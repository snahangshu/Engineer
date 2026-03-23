from pydantic import BaseModel, EmailStr, Field, field_validator
from fastapi import Form
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
    full_name: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[EmailStr] = None
    skill_category: List[str] = []
    specializations: List[str] = []
    preferred_city: Optional[str] = None
    current_location: Optional[str] = None
    pincode: Optional[str] = None
    isAvailable: bool = False

    @field_validator('dob', 'email', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[EmailStr] = None
    skill_category: Optional[List[str]] = None
    specializations: Optional[List[str]] = None
    preferred_city: Optional[str] = None
    current_location: Optional[str] = None
    pincode: Optional[str] = None
    isAvailable: Optional[bool] = None

    @field_validator('dob', 'email', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "" or v is None:
            return None
        return v




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
    account_holder_name: Optional[str] = None


class StatusResponse(BaseModel):
    profile_status: str
    kyc_status: str
    bank_status: str
    overall_status: str
    is_hold: bool
