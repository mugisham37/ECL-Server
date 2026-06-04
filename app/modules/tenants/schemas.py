from datetime import datetime

from pydantic import BaseModel, Field

from app.core.pagination import PageMeta


class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    currency: str
    reporting_cadence: str
    timezone: str


class TenantResponse(BaseModel):
    data: TenantOut


class UpdateTenantRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2)
    currency: str | None = None
    reporting_cadence: str | None = None
    timezone: str | None = None


class MemberOut(BaseModel):
    id: str
    name: str
    email: str
    initials: str
    role: str
    status: str
    last_active: datetime | None
    is_you: bool


class MembersListResponse(BaseModel):
    data: list[MemberOut]
    meta: PageMeta


class UpdateMemberRequest(BaseModel):
    role: str | None = None
    status: str | None = None
