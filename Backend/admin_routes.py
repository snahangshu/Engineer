from datetime import datetime
import profile
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import kyc_collection, bank_collection, profiles_collection, users_collection
from auth_routes import get_current_user
from services.external_engineer_sync import sync_engineer_to_external
from services.interakt_whatsapp import send_whatsapp_message
import schemas
from fastapi import UploadFile, File, Form

router = APIRouter(prefix="/admin", tags=["Admin"])


async def get_admin(current_user=Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return current_user
# --- ADMIN HOME ---
@router.get("/")
async def admin_home(admin=Depends(get_admin)):
    return {"message": "Admin Panel Active"}

@router.get("/engineers")
async def list_engineers(admin=Depends(get_admin)):
    cursor = profiles_collection.aggregate([
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "user"}},
        {"$unwind": "$user"}
    ])
    result = []
    async for doc in cursor:
        result.append({
            "id": str(doc["_id"]),
            "user_id": str(doc["user_id"]),
            "name": doc.get("full_name"),
            "mobile": doc.get("contact_number"),
            "email": doc["user"].get("email"),
            "status": doc.get("status"),
            "is_hold": doc.get("is_hold", True),
            "preferred_city": doc.get("preferred_city"),
            "current_location": doc.get("current_location")
        })

    print(type(result))
    return result



# --- FULL ENGINEER DETAILS ---
@router.get("/engineers/{user_id}")
async def get_engineer_details(user_id: str, admin=Depends(get_admin)):
    uid = ObjectId(user_id)

    user = await users_collection.find_one({"_id": uid})
    profile = await profiles_collection.find_one({"user_id": uid})
    kyc = await kyc_collection.find_one({"user_id": uid})
    bank = await bank_collection.find_one({"user_id": uid})

    if not user:
        raise HTTPException(404, "Engineer not found")
    # #convert IDS
    # user["_id"] = str(user["_id"])
    # if profile:
    #     profile["_id"] = str(profile["_id"])
    #     profile["user_id"] = str(profile["user_id"])
    # if kyc:
    #     kyc["_id"] = str(kyc["_id"])
    #     kyc["user_id"] = str(kyc["user_id"])
    # if bank:
    #     bank["_id"] = str(bank["_id"])
    #     bank["user_id"] = str(bank["user_id"])
    # return {
    #     "user": user,
    #     "profile": profile,
    #     "kyc": kyc,
    #     "bank": bank,
    # }
    return {
        "user": {
            "id": str(user["_id"]),
            "email": profile.get("email") if profile else user.get("email"),
            "role": user.get("role"),
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

            } if profile else None,
        "kyc": {
            "id": str(kyc["_id"]),
            "status": kyc.get("status"),
            # 🔐 Sensitive but masked (safe for admin)
            "aadhaar_number": kyc.get("aadhaar_number"),
            "pan_number": kyc.get("pan_number"),
            "address_proof_type": kyc.get("address_proof_type"),
            "remarks": kyc.get("remarks"),
            "photo_file": kyc.get("photo_file"),               # ✅ KYC photo URL
            "address_proof_file": kyc.get("address_proof_file") # ✅ Address proof URL
        } if kyc else None,

        "bank": {
            "id": str(bank["_id"]),
            "bank_name": bank.get("bank_name"),
            "account_number": bank.get("account_number"),
            "ifsc_code": bank.get("ifsc_code"),
            "status": bank.get("status"),
            "remarks": bank.get("remarks"),
            "proof_file": bank.get("proof_file")               # ✅ Bank proof URL
        } if bank else None
    }
@router.post("/engineers/{user_id}/unhold")
async def unhold_engineer(user_id: str, admin=Depends(get_admin)):
    uid = ObjectId(user_id)

    result = await profiles_collection.update_one(
        {"user_id": uid},
        {
            "$set": {
                "is_hold": False,
                "status": "active",
                "updated_at": datetime.utcnow()
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Engineer profile not found")

    return {"message": "Engineer unhold. KYC & Bank steps enabled."}
   

# --- APPROVE ENGINEER COMPLETELY ---
@router.post("/engineers/{user_id}/approve")
async def approve_engineer(user_id: str, admin=Depends(get_admin)):
    uid = ObjectId(user_id)

    await kyc_collection.update_one(
        {"user_id": uid},
        {"$set": {"status": "approved"}}
    )

    await bank_collection.update_one(
        {"user_id": uid},
        {"$set": {"status": "approved"}}
    )

    await profiles_collection.update_one(
        {"user_id": uid},
        {"$set": {"status": "verified"}}
    )
    # await send_whatsapp_message(
    #     phone=profile["contact_number"],
    #     template_name="engineer_approved",
    #     params=[profile["full_name"]]
    # )
    # 2️⃣ Fetch data for external sync
    user = await users_collection.find_one({"_id": uid})
    profile = await profiles_collection.find_one({"user_id": uid})

    if not user or not profile:
        raise HTTPException(404, "Engineer data incomplete")
    skills = []
    if profile.get("skill_category"):
        skills = profile.get("skill_category")

    # 3️⃣ Prepare payload for external backend
    payload = {
        "engineer_id": str(user["_id"]),
        "name": profile.get("full_name"),
        "mobile": profile.get("contact_number"),
        "email": profile.get("email"),
        #"skills": profile.get("skill_category", []),
        "skills": skills,
        "categories": profile.get("specializations")or [],
        "address": profile.get("preferred_city"),
        "currentLocation": profile.get("current_location"),
        "pincode": profile.get("pincode"),
        "isActive": True,
        "isAvailable": profile.get("isAvailable", False),
    }
    # 4. Validate required fields (important)
    required_fields = ["name", "mobile"]
    for field in required_fields:
        if not payload.get(field):
            raise HTTPException(400, f"Missing field for external sync: {field}")

    # 4️⃣ Push to external backend
    try:
        external_response = await sync_engineer_to_external(payload)
    except Exception as e:
        # IMPORTANT: Do not rollback approvals
        return {
            "message": "Engineer approved, but external sync failed",
            "error": str(e)
        }

    return {
        "message": "Engineer approved and synced successfully",
        "external_response": external_response
    }

# --- REJECT ENGINEER COMPLETELY ---
@router.post("/engineers/{user_id}/reject")
async def reject_engineer(user_id: str, remarks: str | None = None, admin=Depends(get_admin)):
    uid = ObjectId(user_id)
    user = await users_collection.find_one({"_id": uid})
    profile = await profiles_collection.find_one({"user_id": uid})
    if not user or not profile:
        raise HTTPException(404, "Engineer not found")
    await kyc_collection.update_one(
        {"user_id": uid},
        {"$set": {"status": "rejected", "remarks": remarks}}
    )

    await bank_collection.update_one(
        {"user_id": uid},
        {"$set": {"status": "rejected", "remarks": remarks}}
    )

    await profiles_collection.update_one(
        {"user_id": uid},
        {"$set": {"status": "rejected"}}
    )
    # # 📲 Send WhatsApp
    # await send_whatsapp_message(
    #     phone=profile["contact_number"],
    #     template_name="engineer_rejected",
    #     params=[
    #         profile["full_name"],
    #         remarks or "Documents not valid"
    #     ]
    # )
    return {"message": "Engineer rejected"}



@router.post("/kyc/{user_id}/status")
async def update_kyc_status(user_id: str, status: str, remarks: str | None = None, admin=Depends(get_admin)):
    if status not in {"approved", "rejected"}:
        raise HTTPException(400, "Invalid status")
    res = await kyc_collection.update_one(
        {"user_id": ObjectId(user_id)},
        {"$set": {"status": status, "remarks": remarks}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "KYC not found")
    return {"message": "KYC status updated"}


@router.post("/bank/{user_id}/status")
async def update_bank_status(user_id: str, status: str, remarks: str | None = None, admin=Depends(get_admin)):
    if status not in {"approved", "rejected"}:
        raise HTTPException(400, "Invalid status")
    res = await bank_collection.update_one(
        {"user_id": ObjectId(user_id)},
        {"$set": {"status": status, "remarks": remarks}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Bank record not found")
    return {"message": "Bank status updated"}


# --- ADMIN EDIT/UPLOAD CAPABILITIES ---

@router.put("/engineers/{user_id}/profile")
async def admin_update_engineer_profile(user_id: str, payload: schemas.ProfileCreate, admin=Depends(get_admin)):
    uid = ObjectId(user_id)
    data = payload.dict()
    if data.get("dob"):
        data["dob"] = datetime.combine(data["dob"], datetime.min.time())
    
    data.update({"updated_at": datetime.utcnow()})
    
    result = await profiles_collection.update_one({"user_id": uid}, {"$set": data})
    if result.matched_count == 0:
        raise HTTPException(404, "Engineer profile not found")
    
    return {"message": "Engineer profile updated successfully"}


from fastapi import UploadFile, File
from cloudinary_client import upload_file_to_cloudinary

@router.post("/engineers/{user_id}/kyc")
async def admin_upload_engineer_kyc(
    user_id: str,
    aadhaar_number: str = Form(...),
    pan_number: str = Form(...),
    address_proof_type: str = Form(...),
    address_proof_file: UploadFile = File(None),
    photo_file: UploadFile = File(None),
    admin=Depends(get_admin)
):
    uid = ObjectId(user_id)
    user_id_str = str(user_id)
    
    data = {
        "aadhaar_number": aadhaar_number[-4:].rjust(len(aadhaar_number), "X") if "X" not in aadhaar_number else aadhaar_number,
        "pan_number": pan_number,
        "address_proof_type": address_proof_type,
        "updated_at": datetime.utcnow()
    }

    if address_proof_file:
        address_url = upload_file_to_cloudinary(
            address_proof_file.file,
            folder="door2fy/kyc/address",
            public_id=f"{user_id_str}_address"
        )
        data["address_proof_file"] = address_url

    if photo_file:
        photo_url = upload_file_to_cloudinary(
            photo_file.file,
            folder="door2fy/kyc/photo",
            public_id=f"{user_id_str}_photo"
        )
        data["photo_file"] = photo_url

    await kyc_collection.update_one({"user_id": uid}, {"$set": data}, upsert=True)
    return {"message": "KYC documents uploaded/updated successfully"}


@router.post("/engineers/{user_id}/bank")
async def admin_upload_engineer_bank(
    user_id: str,
    bank_name: str = Form(...),
    account_number: str = Form(...),
    ifsc_code: str = Form(...),
    proof_file: UploadFile = File(None),
    admin=Depends(get_admin)
):
    uid = ObjectId(user_id)
    user_id_str = str(user_id)
    
    data = {
        "bank_name": bank_name,
        "account_number": account_number,
        "ifsc_code": ifsc_code,
        "updated_at": datetime.utcnow()
    }

    if proof_file:
        proof_url = upload_file_to_cloudinary(
            proof_file.file,
            folder="door2fy/bank",
            public_id=f"{user_id_str}_bank_proof"
        )
        data["proof_file"] = proof_url

    await bank_collection.update_one({"user_id": uid}, {"$set": data}, upsert=True)
    return {"message": "Bank details/documents updated successfully"}
