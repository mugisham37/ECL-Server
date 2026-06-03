from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserProfileOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    tenant_id: str
    tenant_name: str
    is_email_verified: bool
    initials: str


class MembershipOut(BaseModel):
    tenant_id: str
    tenant_name: str
    role: str
    status: str


class MeData(BaseModel):
    user: UserProfileOut
    memberships: list[MembershipOut]


class MeResponse(BaseModel):
    data: MeData


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class SessionOut(BaseModel):
    id: str
    device_type: str
    device_name: str | None
    last_active_at: datetime
    current: bool


class SessionsResponse(BaseModel):
    data: list[SessionOut]
