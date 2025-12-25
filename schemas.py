from pydantic import BaseModel, EmailStr, Field
from fastapi import Form
from typing import Optional
from typing import Optional, List
from datetime import date


class RegisterRequest(BaseModel):
    mode: str = Field(..., pattern="^(mobile|email)$")
    mobile: Optional[str] = None
    email: Optional[EmailStr] = None


class VerifyOtpRequest(BaseModel):
    identifier: str
    otp: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileCreate(BaseModel):
    full_name: str
    dob: date
    gender: str
    contact_number: str
    email: EmailStr
    skill_category:List[str] = []
    specializations: List[str] = []
    preferred_city: str
    current_location: str
    isAvailable: bool = False
class KYCForm:
    def __init__(
        self,
        aadhaar_number: str = Form(..., min_length=12, max_length=12),
        pan_number: str = Form(..., min_length=10, max_length=10),
        address_proof_type: str = Form(...),
    ):
        self.aadhaar_number = aadhaar_number
        self.pan_number = pan_number
        self.address_proof_type = address_proof_type

class BankDetailsCreate(BaseModel):
    bank_name: str
    account_number: str
    ifsc_code: str


class StatusResponse(BaseModel):
    profile_status: str
    kyc_status: str
    bank_status: str
    overall_status: str
