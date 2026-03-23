import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import json

async def main():
    MONGO_URI = "mongodb+srv://door2fy:door2fy@cluster0.z5i6p.mongodb.net/door2fy"
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["door2fy"]
    profiles_collection = db["profiles"]

    profile = await profiles_collection.find_one({})
    if profile:
        profile["_id"] = str(profile["_id"])
        profile["user_id"] = str(profile["user_id"])
        print(json.dumps(profile, default=str))
    else:
        print("No profile found")

if __name__ == "__main__":
    asyncio.run(main())
