from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class AcceptInviteRequest(BaseModel):
    token: str
    name: str = Field(min_length=2)
    password: str = Field(min_length=8)


class SendInviteRequest(BaseModel):
    email: EmailStr
    role: str
    tenant_id: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class InviteValidateData(BaseModel):
    email: str
    tenant_name: str
    inviter_name: str
    role: str
    expires_at: datetime


class InviteValidateResponse(BaseModel):
    data: InviteValidateData
