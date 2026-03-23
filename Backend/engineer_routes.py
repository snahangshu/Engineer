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
    payload: schemas.ProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["_id"]
    existing = await profiles_collection.find_one({"user_id": user_id})
    
    # Filter out None values to support partial updates
    data = {k: v for k, v in payload.dict().items() if v is not None}
    
    # Fix : Convert date --> datetime for mongodb
    if data.get("dob"):
        data["dob"] = datetime.combine(data["dob"], datetime.min.time())
    
    data.update({
        "user_id": user_id,
        "updated_at": datetime.utcnow()
    })
    
    if existing:
        await profiles_collection.update_one({"_id": existing["_id"]}, {"$set": data})
    else:
        # 🆕 FIRST-TIME PROFILE CREATION
        # For first-time, we might want to ensure some required fields, 
        # but let's assume the frontend handles this for now or validate here.
        required_fields = ["full_name", "contact_number", "email", "preferred_city"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(400, f"Missing required field: {field}")
                
        data.update({
            "created_at": datetime.utcnow(),
            "status": "pending",
            "is_hold": True      # ✅ HOLD ENGINEER AFTER PROFILE
        })

        await profiles_collection.insert_one(data)
    
    # ✅ ALWAYS FETCH FRESH STATE
    profile = await profiles_collection.find_one({"user_id": user_id})
    return {
        "message": "Profile saved Successfully",
        "is_hold": profile.get("is_hold", True),
        "status": profile.get("status")
    }



@router.post("/kyc")
async def upload_kyc(
    kyc: KYCForm = Depends(),   # ✅ schema added
    address_proof_file: UploadFile = File(None), # Made optional
    photo_file: UploadFile = File(None),       # Made optional
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
    
    # 🔍 Fetch existing to maintain files
    existing = await kyc_collection.find_one({"user_id": user_id})
    
    data = {
        "user_id": user_id,
        "aadhaar_number": kyc.aadhaar_number[-4:].rjust(len(kyc.aadhaar_number), "X") if "X" not in kyc.aadhaar_number else kyc.aadhaar_number,
        "pan_number": kyc.pan_number,
        "address_proof_type": kyc.address_proof_type,
        "status": "pending",
        "updated_at": datetime.utcnow(),
    }

    # Upload address proof if provided
    if address_proof_file:
        address_url = upload_file_to_cloudinary(
            address_proof_file.file,
            folder="door2fy/kyc/address",
            public_id=f"{user_id_str}_address"
        )
        data["address_proof_file"] = address_url
    elif existing and "address_proof_file" in existing:
        data["address_proof_file"] = existing["address_proof_file"]

    # Upload photo if provided
    if photo_file:
        photo_url = upload_file_to_cloudinary(
            photo_file.file,
            folder="door2fy/kyc/photo",
            public_id=f"{user_id_str}_photo"
        )
        data["photo_file"] = photo_url
    elif existing and "photo_file" in existing:
        data["photo_file"] = existing["photo_file"]

    await kyc_collection.update_one(
        {"user_id": user_id},
        {"$set": data},
        upsert=True
    )

    return {"message": "KYC uploaded/updated, pending verification"}


@router.post("/bank")
async def save_bank_details(
    bank_name: str = Form(...),
    account_number: str = Form(...),
    ifsc_code: str = Form(...),
    account_holder_name: str = Form(None), # Optional but supported
    proof_file: UploadFile = File(None),   # Made optional
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
    
    # 🔍 Fetch existing
    existing = await bank_collection.find_one({"user_id": user_id})

    data = {
        "user_id": user_id,
        "bank_name": bank_name,
        "account_number": account_number,
        "ifsc_code": ifsc_code,
        "status": "pending",
        "updated_at": datetime.utcnow(),
    }
    
    if account_holder_name:
        data["account_holder_name"] = account_holder_name
    elif existing and "account_holder_name" in existing:
        data["account_holder_name"] = existing["account_holder_name"]

    # Upload bank proof if provided
    if proof_file:
        proof_url = upload_file_to_cloudinary(
            proof_file.file,
            folder="door2fy/bank",
            public_id=f"{user_id_str}_bank_proof"
        )
        data["proof_file"] = proof_url
    elif existing and "proof_file" in existing:
        data["proof_file"] = existing["proof_file"]

    await bank_collection.update_one(
        {"user_id": user_id},
        {"$set": data},
        upsert=True
    )

    return {"message": "Bank details updated, pending verification"}


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
    kyc_status = kyc["status"] if kyc else "incomplete"
    bank_status = bank["status"] if bank else "incomplete"
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


@router.get("/details")
async def get_engineer_details_self(current_user: dict = Depends(get_current_user)):
    user_id = current_user["_id"]
    
    profile = await profiles_collection.find_one({"user_id": user_id})
    kyc = await kyc_collection.find_one({"user_id": user_id})
    bank = await bank_collection.find_one({"user_id": user_id})

    return {
        "user": {
            "id": str(current_user["_id"]),
            "email": current_user.get("email"),
            "role": current_user.get("role"),
        },
        "profile": {
            "id": str(profile["_id"]),
            "name": profile.get("full_name"),
            "phone": profile.get("contact_number"),
            "email": profile.get("email"),
            "skills": profile.get("skill_category", []),
            "specializations": profile.get("specializations") or profile.get("specialization") or [],
            "preferred_city": profile.get("preferred_city"),
            "current_location": profile.get("current_location"),
            "pincode": profile.get("pincode"),
            "isAvailable": profile.get("isAvailable") if "isAvailable" in profile else profile.get("willing_to_relocate", False),
            "status": profile.get("status", "pending"),
            "is_hold": profile.get("is_hold", False),

            "dob": profile.get("dob").date() if profile.get("dob") and hasattr(profile.get("dob"), "date") else profile.get("dob"),
            "gender": profile.get("gender"),
        } if profile else None,
        "kyc": {
            "id": str(kyc["_id"]),
            "status": kyc.get("status"),
            "aadhaar_number": kyc.get("aadhaar_number"),
            "pan_number": kyc.get("pan_number"),
            "address_proof_type": kyc.get("address_proof_type"),
            "remarks": kyc.get("remarks"),
            "photo_file": kyc.get("photo_file"),
            "address_proof_file": kyc.get("address_proof_file")
        } if kyc else None,
        "bank": {
            "id": str(bank["_id"]),
            "bank_name": bank.get("bank_name"),
            "account_number": bank.get("account_number"),
            "ifsc_code": bank.get("ifsc_code"),
            "account_holder_name": bank.get("account_holder_name"),
            "status": bank.get("status"),
            "remarks": bank.get("remarks"),
            "proof_file": bank.get("proof_file")
        } if bank else None
    }
