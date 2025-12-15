from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
import os
from datetime import datetime
from bson import ObjectId
#from s3_client import upload_file_to_s3
from cloudinary_client import upload_file_to_cloudinary



from database import profiles_collection,kyc_collection,bank_collection
from auth_routes import get_current_user
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
        data["created_at"] = datetime.utcnow()
        await profiles_collection.insert_one(data)

    return {"message": "Profile saved"}


@router.post("/kyc")
async def upload_kyc(
    aadhaar_number: str = Form(...),
    pan_number: str = Form(...),
    address_proof_type: str = Form(...),
    address_proof_file: UploadFile = File(...),
    photo_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["_id"]
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
        "aadhaar_number": aadhaar_number[-4:].rjust(len(aadhaar_number), "X"),
        "pan_number": pan_number,
        "address_proof_type": address_proof_type,
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
    payload: schemas.BankDetailsCreate,
    proof_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["_id"]
    user_id_str = str(user_id)  # ✅ convert ObjectId to string

    # Upload bank proof to Cloudinary
    proof_url = upload_file_to_cloudinary(
        proof_file.file,
        folder="door2fy/bank",
        public_id=f"{user_id_str}_bank_proof"
    )

    data = {
        "user_id": user_id,
        "bank_name": payload.bank_name,
        "account_number": payload.account_number,
        "ifsc_code": payload.ifsc_code,
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

    profile_status = "completed" if profile else "pending"
    kyc_status = kyc["status"] if kyc else "pending"
    bank_status = bank["status"] if bank else "pending"

     # FINAL OVERALL STATUS LOGIC
    if profile_status == "completed" and kyc_status == "approved" and bank_status == "approved":
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
    )
