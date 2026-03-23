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
    allow_origins=[
        "https://partner.door2fy.in",
        "https://eng.door2fy.in",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],

    allow_headers=["*"],
)




app.include_router(auth_router)
app.include_router(engineer_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    return {"message": "Door2Fy backend running"}
