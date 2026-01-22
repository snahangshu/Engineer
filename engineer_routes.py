from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
import os
from datetime import datetime
from bson import ObjectId
#from s3_client import upload_file_to_s3
from cloudinary_client import upload_file_to_cloudinary
from database import profiles_collection,kyc_collection,bank_collection
from auth_routes import get_current_user
from schemas import KYCForm
from fastapi import UploadFile, File, Depends
import schemas

router = APIRouter(prefix="/engineer", tags=["Engineer"])

UPLOAD_ROOT = "uploads"
os.makedirs(os.path.join(UPLOAD_ROOT, "kyc"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_ROOT, "bank"), exist_ok=True)


@router.post("/profile")
async def create_or_update_profile(
    payload: schemas.ProfileCreate,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["_id"]
    existing = await profiles_collection.find_one({"user_id": user_id})
    data = payload.dict()
    # data.update({
    #     "user_id": user_id,
    #     "updated_at": datetime.utcnow()
    # })
    # Fix : Convert date --> datetime for mongodb
    if data.get("dob"):
        data["dob"] = datetime.combine(data["dob"], datetime.min.time())
    data.update({
        "user_id": user_id,"updated_at": datetime.utcnow()}
        )
    
    if existing:
        await profiles_collection.update_one({"_id": existing["_id"]}, {"$set": data})
    else:
        # 🆕 FIRST-TIME PROFILE CREATION
        data.update({
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "status": "pending",
            "is_hold": True      # ✅ HOLD ENGINEER AFTER PROFILE
        })

        await profiles_collection.insert_one(data)
    # ✅ ALWAYS FETCH FRESH STATE
    profile = await profiles_collection.find_one({"user_id": user_id})
    return {"message": "Profile saved Successfully",
        "is_hold": profile.get("is_hold", True),"status": profile.get("status")}


@router.post("/kyc")
async def upload_kyc(
    kyc: KYCForm = Depends(),   # ✅ schema added
    address_proof_file: UploadFile = File(...),
    photo_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["_id"]
     # ================== HOLD CHECK (ADD HERE) ==================
    profile = await profiles_collection.find_one({"user_id": user_id})

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Profile not completed"
        )

    if profile.get("is_hold", True):
        raise HTTPException(
            status_code=403,
            detail="Your profile is under review. Please wait for admin approval."
        )
    # ===================================================
    user_id_str = str(user_id)  # ✅ IMPORTANT

    # Upload address proof
    address_url = upload_file_to_cloudinary(
        address_proof_file.file,
        folder="door2fy/kyc/address",
        public_id=f"{user_id_str}_address"
    )

    # Upload photo
    photo_url = upload_file_to_cloudinary(
        photo_file.file,
        folder="door2fy/kyc/photo",
        public_id=f"{user_id_str}_photo"
    )

    data = {
        "user_id": user_id,
        "aadhaar_number": kyc.aadhaar_number[-4:].rjust(len(kyc.aadhaar_number), "X"),
        "pan_number": kyc.pan_number,
        "address_proof_type": kyc.address_proof_type,
        "address_proof_file": address_url,
        "photo_file": photo_url,
        "status": "pending",
        "updated_at": datetime.utcnow(),
    }

    await kyc_collection.update_one(
        {"user_id": user_id},
        {"$set": data},
        upsert=True
    )

    return {"message": "KYC uploaded, pending verification"}


@router.post("/bank")
async def save_bank_details(
    # payload: schemas.BankDetailsCreate,
    bank_name: str = Form(...),
    account_number: str = Form(...),
    ifsc_code: str = Form(...),
    proof_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["_id"]
    # ================== HOLD CHECK (ADD HERE) ==================
    profile = await profiles_collection.find_one({"user_id": user_id})

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Profile not completed"
        )

    if profile.get("is_hold", True):
        raise HTTPException(
            status_code=403,
            detail="Your profile is under review. Bank details cannot be submitted yet."
        )
    # ============================================================
    user_id_str = str(user_id)  # ✅ convert ObjectId to string

    # Upload bank proof to Cloudinary
    proof_url = upload_file_to_cloudinary(
        proof_file.file,
        folder="door2fy/bank",
        public_id=f"{user_id_str}_bank_proof"
    )

    data = {
        "user_id": user_id,
        "bank_name": bank_name,
        "account_number": account_number,
        "ifsc_code": ifsc_code,
        "proof_file": proof_url,
        "status": "pending",
        "updated_at": datetime.utcnow(),
    }

    await bank_collection.update_one(
        {"user_id": user_id},
        {"$set": data},
        upsert=True
    )

    return {"message": "Bank details submitted, pending verification"}


@router.get("/status", response_model=schemas.StatusResponse)
async def get_status(current_user: dict = Depends(get_current_user)):
    user_id = current_user["_id"]

    profile = await profiles_collection.find_one({"user_id": user_id})
    kyc = await kyc_collection.find_one({"user_id": user_id})
    bank = await bank_collection.find_one({"user_id": user_id})

    if not profile:
        profile_status = "pending"
        is_hold = True
    else:
        is_hold = profile.get("is_hold", True)
        profile_status = "pending" if is_hold else "active"
    kyc_status = kyc["status"] if kyc else "pending"
    bank_status = bank["status"] if bank else "pending"
    # is_hold = profile.get("is_hold", True) if profile else True
     # FINAL OVERALL STATUS LOGIC
    if not is_hold and kyc_status == "approved" and bank_status == "approved":
        overall = "verified"
    elif kyc_status == "rejected" or bank_status == "rejected":
        overall = "rejected"
    else:
        overall = "pending_review"

    return schemas.StatusResponse(
        profile_status=profile_status,
        kyc_status=kyc_status,
        bank_status=bank_status,
        overall_status=overall,
        is_hold=is_hold
    )
