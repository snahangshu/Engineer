from fastapi import APIRouter, HTTPException, Depends
from datetime import timedelta
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
                "verified": {"mobile": False, "email": False}
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
                "verified": {"mobile": False, "email": False}
            })
            user_id = res.inserted_id
        else:
            user_id = user["_id"]

    otp = generate_otp()
    session_id = str(user_id)

    # For now we just log OTP in server; in real app send via SMS / email
    OTP_STORE[session_id] = {"otp": otp, "identifier": identifier}
    print("DEBUG OTP for", identifier, "=", otp)

    return {"session_id": session_id, "message": "OTP sent (debug: check logs)"}


@router.post("/verify-otp", response_model=schemas.TokenResponse)
async def verify_otp(req: schemas.VerifyOtpRequest):
    data = OTP_STORE.get(req.session_id)
    if not data or data["otp"] != req.otp:
        raise HTTPException(400, "Invalid OTP")

    user_id = ObjectId(req.session_id)
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

    token = create_access_token({"sub": str(user_id)})
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