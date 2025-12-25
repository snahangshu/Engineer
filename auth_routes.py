from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime,timedelta
import uuid
import schemas
from database import users_collection
from utils import create_access_token
from bson import ObjectId
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from utils import SECRET_KEY, ALGORITHM
from services.twilio_otp import send_otp, verify_otp as twilio_verify_otp


security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["Auth"])

# In-memory OTP store for demo; use Redis in production
#OTP_STORE: dict[str, dict] = {}

#========================Register/Send Otp===============
@router.post("/register")
async def register(req: schemas.RegisterRequest):
    # ================= ADMIN REGISTER BYPASS =================
    if req.mode == "mobile" and req.mobile == "9612686019":
        user = await users_collection.find_one({"mobile": "9612686019"})

        if not user:
            res = await users_collection.insert_one({
                "mobile": "9612686019",
                "email": None,
                "verified": {"mobile": True, "email": False},
                "role": "admin",
                "created_at": datetime.utcnow()
            })
            user_id = res.inserted_id

        return {
            "identifier": f"+91{9612686019}",
            "is_new_user": False,
            "message": "Admin OTP required"
        }
    if req.mode == "mobile":
        if not req.mobile:
            raise HTTPException(400, "Mobile is required")
        identifier = f"+91{req.mobile}"  #Important : Country code
        channel = "sms"
        user = await users_collection.find_one({"mobile": req.mobile})
        if not user:
            res = await users_collection.insert_one({
                "mobile": req.mobile,
                "email": None,
                "verified": {"mobile": False, "email": False},
                "created_at": datetime.utcnow()
            })
            user_id = res.inserted_id
            is_new_user = True
        else:
            user_id = user["_id"]
            is_new_user = False
    else:
        if not req.email:
            raise HTTPException(400, "Email is required")
        identifier = req.email
        channel = "email"
        user = await users_collection.find_one({"email": req.email})
        if not user:
            res = await users_collection.insert_one({
                "mobile": None,
                "email": req.email,
                "verified": {"mobile": False, "email": False},
                "created_at": datetime.utcnow()
            })
            user_id = res.inserted_id
            is_new_user = True
        else:
            user_id = user["_id"]
            is_new_user = False
    # Send OTP via Twilio
    send_otp(identifier, channel)
    return{"identifier":identifier,"is_new_user":is_new_user,"message":"OTP sent via "+channel}


    # otp = generate_otp()
    #session_id = str(uuid.uuid4())# unique per otp flow

    # For now we just log OTP in server; in real app send via SMS / email
    #OTP_STORE[session_id] = {"otp": otp, "user_id":str(user_id),"expires_at": datetime.utcnow() + timedelta(minutes=5)}
    #print("DEBUG OTP for", identifier, "=", otp)

    #return {"session_id": session_id,"is_new_user":not bool(user), "message": "OTP sent (debug: check logs)"}

#========================Verify Otp===============
@router.post("/verify-otp", response_model=schemas.TokenResponse)
async def verify_otp(req: schemas.VerifyOtpRequest):
    # data = OTP_STORE.get(req.session_id)
    # if not data or data["otp"] != req.otp:
    #     raise HTTPException(400, "Invalid OTP")
    # if datetime.utcnow() > data["expires_at"]:
    #     OTP_STORE.pop(req.session_id, None)
    #     raise HTTPException(400, "OTP expired")
    # ================= ADMIN OTP BYPASS =================
    if req.identifier.endswith("9612686019"):
        if req.otp != "123456":
            raise HTTPException(400, "Invalid admin OTP")

        user = await users_collection.find_one({"mobile": "9612686019"})
        if not user:
            raise HTTPException(404, "Admin user not found")

        await users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "verified.mobile": True,
                "role": "admin"
            }}
        )

        token = create_access_token({
            "sub": str(user["_id"]),
            "role": "admin"
        })

        return schemas.TokenResponse(access_token=token)

    # ================= ENGINEER (TWILIO OTP) =================

    # ================= NORMAL USER (TWILIO) =================
    is_valid = twilio_verify_otp(req.identifier, req.otp)
    if not  is_valid:
        raise HTTPException(400, "Invalid OTP")
    #find user
    #user_id = ObjectId(data["user_id"])
    user = await users_collection.find_one({"$or":[{"mobile":req.identifier[-10:]},
                                                   {"email":req.identifier}]})
    
    if not user:
        raise HTTPException(404, "User not found")
    #update verification + role
    
    # Mark verified
    update = {}
    if user.get("mobile"):
        update["verified.mobile"] = True
    if user.get("email"):
        update["verified.email"] = True
        # Assign roles
    update["role"] = "admin" if user.get("email") == "snahangshu@door2fy.in" else "engineer"
    await users_collection.update_one({"_id": user["_id"]}, {"$set": update})
    # if update:
    #     await users_collection.update_one({"_id": user_id}, {"$set": update})
    # OTP_STORE.pop(req.session_id, None)  # ✅ cleanup
    #Issue JwT
    token = create_access_token({"sub": str(user["_id"]),"role": update["role"]})
    return schemas.TokenResponse(access_token=token)
#========================Get Current User================
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    cred_exc = HTTPException(
        status_code=401,
        detail="Could not validate credentials"
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise cred_exc
    except JWTError:
        raise cred_exc

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise cred_exc

    return user