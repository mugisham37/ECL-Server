from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.pagination import PageMeta


class PlatformTenantOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    created_at: datetime
    mrr: float = 0.0
    region: str | None = None
    runs_count: int = 0


class PlatformTenantsResponse(BaseModel):
    data: list[PlatformTenantOut]
    meta: PageMeta


class CreatePlatformTenantRequest(BaseModel):
    name: str
    admin_email: EmailStr
    admin_name: str
    plan: str = "trial"
    region: str | None = None
    start_trial: bool = False


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
    tenant_name: str | None = None
    role: str | None = None
    last_active_at: datetime | None = None


class PlatformUsersResponse(BaseModel):
    data: list[PlatformUserOut]
    meta: PageMeta


class UpdatePlatformUserRequest(BaseModel):
    is_active: bool | None = None


class PlatformKPIs(BaseModel):
    tenants_total: int
    tenants_active: int
    tenants_trial: int
    tenants_suspended: int
    runs_this_month: int
    runs_today: int
    mrr_total_usd: float


class TrendPoint(BaseModel):
    date: str
    runs: int


class TenantsByPlan(BaseModel):
    trial: int
    starter: int
    growth: int
    enterprise: int


class PlatformOverviewOut(BaseModel):
    kpis: PlatformKPIs
    uptime_30d: str
    trend_14d: list[TrendPoint]
    tenants_by_plan: TenantsByPlan
    recent_audit: list[dict]


class PlatformOverviewResponse(BaseModel):
    data: PlatformOverviewOut


class AdminSummary(BaseModel):
    id: str
    name: str
    email: str
    initials: str


class TenantDetailOut(BaseModel):
    id: str
    name: str
    mark: str
    plan: str
    status: str
    created_at: datetime
    users_count: int
    runs_this_month: int
    mrr: float
    engine_version_pin: str | None
    region: str | None
    admins: list[AdminSummary]
    status_note: str


class TenantDetailResponse(BaseModel):
    data: TenantDetailOut


class SuspendTenantRequest(BaseModel):
    reason: str | None = None


class ExtendTrialRequest(BaseModel):
    days: int = Field(ge=1, le=90)


class ImpersonateResponse(BaseModel):
    data: dict[str, str]
    message: str


class ServiceStatus(BaseModel):
    name: str
    state: str
    value: str


class QueueStats(BaseModel):
    running: int
    queued: int
    avg_wait_seconds: int


class SystemHealthOut(BaseModel):
    services: list[ServiceStatus]
    queue_stats: QueueStats
    overall_state: str
    recent_errors: list[dict]


class SystemHealthResponse(BaseModel):
    data: SystemHealthOut


class EngineVersionOut(BaseModel):
    id: str
    version: str
    is_current: bool
    release_date: date
    changelog: list[str]
    tenants_pinned: int
    created_at: datetime


class EngineVersionListOut(BaseModel):
    versions: list[EngineVersionOut]
    total: int


class EngineVersionListResponse(BaseModel):
    data: EngineVersionListOut
