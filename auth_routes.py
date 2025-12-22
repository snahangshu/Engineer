from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime,timedelta
import uuid
import schemas
from database import users_collection
from utils import create_access_token, generate_otp
from bson import ObjectId
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from utils import SECRET_KEY, ALGORITHM


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")#not actually used

router = APIRouter(prefix="/auth", tags=["Auth"])

# In-memory OTP store for demo; use Redis in production
OTP_STORE: dict[str, dict] = {}


@router.post("/register")
async def register(req: schemas.RegisterRequest):
    if req.mode == "mobile":
        if not req.mobile:
            raise HTTPException(400, "Mobile is required")
        identifier = req.mobile
        user = await users_collection.find_one({"mobile": req.mobile})
        if not user:
            res = await users_collection.insert_one({
                "mobile": req.mobile,
                "email": None,
                "verified": {"mobile": False, "email": False},
                "created_at": datetime.utcnow()
            })
            user_id = res.inserted_id
        else:
            user_id = user["_id"]
    else:
        if not req.email:
            raise HTTPException(400, "Email is required")
        identifier = req.email
        user = await users_collection.find_one({"email": req.email})
        if not user:
            res = await users_collection.insert_one({
                "mobile": None,
                "email": req.email,
                "verified": {"mobile": False, "email": False},
                "created_at": datetime.utcnow()
            })
            user_id = res.inserted_id
        else:
            user_id = user["_id"]

    otp = generate_otp()
    session_id = str(uuid.uuid4())# unique per otp flow

    # For now we just log OTP in server; in real app send via SMS / email
    OTP_STORE[session_id] = {"otp": otp, "user_id":str(user_id),"expires_at": datetime.utcnow() + timedelta(minutes=5)}
    print("DEBUG OTP for", identifier, "=", otp)

    return {"session_id": session_id,"is_new_user":not bool(user), "message": "OTP sent (debug: check logs)"}


@router.post("/verify-otp", response_model=schemas.TokenResponse)
async def verify_otp(req: schemas.VerifyOtpRequest):
    data = OTP_STORE.get(req.session_id)
    if not data or data["otp"] != req.otp:
        raise HTTPException(400, "Invalid OTP")
    if datetime.utcnow() > data["expires_at"]:
        OTP_STORE.pop(req.session_id, None)
        raise HTTPException(400, "OTP expired")

    user_id = ObjectId(data["user_id"])
    user = await users_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(404, "User not found")

    # Mark verified
    update = {}
    if user.get("mobile"):
        update["verified.mobile"] = True
    if user.get("email"):
        update["verified.email"] = True
        # Assign roles
    if user.get("email") == "admin@door2fy.in":
        update["role"] = "admin"
    else:
        update["role"] = "engineer"

    if update:
        await users_collection.update_one({"_id": user_id}, {"$set": update})
    OTP_STORE.pop(req.session_id, None)  # ✅ cleanup

    token = create_access_token({"sub": str(user_id),"role": update["role"]})
    return schemas.TokenResponse(access_token=token)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    cred_exc = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise cred_exc
    except JWTError:
        raise cred_exc
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise cred_exc
    return user