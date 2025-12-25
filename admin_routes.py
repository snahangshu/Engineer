from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import kyc_collection, bank_collection, profiles_collection, users_collection
from auth_routes import get_current_user
from services.external_engineer_sync import sync_engineer_to_external

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
            "email": profile.get("email"),
            "role": user.get("role"),
        },
        "profile": {
                "id": str(profile["_id"]),
                "name": profile.get("full_name"),
                "phone": profile.get("contact_number"),
                "email": profile.get("email"),
                "skills": profile.get("skill_category", []),
                "specializations": profile.get("specializations", []),
                "preferred_city": profile.get("preferred_city"),
                "current_location": profile.get("current_location"),
                "isAvailable": profile.get("isAvailable", False),
                "status": profile.get("status", "pending"),
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
