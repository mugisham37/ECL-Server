from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.core.pagination import PageMeta


class PlatformTenantOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    created_at: datetime


class PlatformTenantsResponse(BaseModel):
    data: list[PlatformTenantOut]
    meta: PageMeta


class CreatePlatformTenantRequest(BaseModel):
    name: str
    admin_email: EmailStr
    admin_name: str
    plan: str = "trial"


class UpdatePlatformTenantRequest(BaseModel):
    name: str | None = None
    plan: str | None = None
    status: str | None = None


class PlatformUserOut(BaseModel):
    id: str
    name: str
    email: str
    is_active: bool
    is_platform_admin: bool
    last_login_at: datetime | None


class PlatformUsersResponse(BaseModel):
    data: list[PlatformUserOut]
    meta: PageMeta


class UpdatePlatformUserRequest(BaseModel):
    is_active: bool | None = None
