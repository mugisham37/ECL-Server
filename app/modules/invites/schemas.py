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


class BatchInviteItem(BaseModel):
    email: EmailStr
    role: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class BatchInviteRequest(BaseModel):
    invites: list[BatchInviteItem] = Field(min_length=1, max_length=20)
    tenant_id: str


class BatchInviteOut(BaseModel):
    id: str
    email: str
    role: str


class BatchInviteResponse(BaseModel):
    data: list[BatchInviteOut]
    message: str


class InviteListItemOut(BaseModel):
    id: str
    email: str
    role: str
    status: str
    created_at: datetime
    expires_at: datetime
    invited_by_name: str | None


class InviteListResponse(BaseModel):
    data: list[InviteListItemOut]
