from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "door2fy")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

users_collection = db["users"]
profiles_collection = db["profiles"]
kyc_collection = db["kyc_documents"]
bank_collection = db["bank_details"]


# Helper to convert Mongo ObjectId to string for JSON
def obj_id(o):
    if isinstance(o, ObjectId):
        return str(o)
    return o
