from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from auth_routes import router as auth_router
from engineer_routes import router as engineer_router
from admin_routes import router as admin_router

app = FastAPI(title="Door2Fy Associate Engineer Backend")
# CORS for your React/Next/other frontend
# origins = [
#     "http://localhost:8080",
#     "https://partner.door2fy.in/",
# ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://partner.door2fy.in"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(engineer_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    return {"message": "Door2Fy backend running"}
