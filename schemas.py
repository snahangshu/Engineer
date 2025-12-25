from pydantic import BaseModel, EmailStr, Field
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
    willing_to_relocate: bool = False


class BankDetailsCreate(BaseModel):
    bank_name: str
    account_number: str
    ifsc_code: str


class StatusResponse(BaseModel):
    profile_status: str
    kyc_status: str
    bank_status: str
    overall_status: str
