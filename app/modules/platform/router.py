from fastapi import APIRouter, Depends, status

from app.core.pagination import PageParams
from app.dependencies import CurrentUser, DbSession, PlatformAdmin
from app.modules.platform.schemas import (
    CreatePlatformTenantRequest,
    EngineVersionListResponse,
    ExtendTrialRequest,
    ImpersonateResponse,
    PlatformOverviewResponse,
    PlatformTenantsResponse,
    PlatformUsersResponse,
    SuspendTenantRequest,
    SystemHealthResponse,
    TenantDetailResponse,
    UpdatePlatformTenantRequest,
    UpdatePlatformUserRequest,
)
from app.modules.platform import service

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/overview")
async def platform_overview(
    db: DbSession,
    _admin: PlatformAdmin,
) -> PlatformOverviewResponse:
    data = await service.get_platform_overview(db)
    return PlatformOverviewResponse(data=data)


@router.get("/tenants")
async def list_platform_tenants(
    db: DbSession,
    _admin: PlatformAdmin,
    params: PageParams = Depends(),
    status_filter: str | None = None,
) -> PlatformTenantsResponse:
    data, meta = await service.list_platform_tenants(db, params, status_filter)
    return PlatformTenantsResponse(data=data, meta=meta)


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_platform_tenant(
    body: CreatePlatformTenantRequest,
    db: DbSession,
    admin: PlatformAdmin,
) -> dict[str, object]:
    result = await service.create_platform_tenant(db, body, admin.id)
    return {"data": result, "message": "Tenant created."}


@router.get("/tenants/{tenant_id}")
async def get_tenant_detail(
    tenant_id: str,
    db: DbSession,
    _admin: PlatformAdmin,
) -> TenantDetailResponse:
    data = await service.get_tenant_detail(db, tenant_id)
    return TenantDetailResponse(data=data)


@router.patch("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def patch_platform_tenant(
    tenant_id: str,
    body: UpdatePlatformTenantRequest,
    db: DbSession,
    _admin: PlatformAdmin,
) -> None:
    await service.patch_platform_tenant(db, tenant_id, body)


@router.post("/tenants/{tenant_id}/suspend", status_code=status.HTTP_204_NO_CONTENT)
async def suspend_tenant_endpoint(
    tenant_id: str,
    body: SuspendTenantRequest,
    db: DbSession,
    admin: PlatformAdmin,
) -> None:
    await service.suspend_tenant(db, tenant_id, admin.id, body.reason)


@router.post("/tenants/{tenant_id}/reactivate", status_code=status.HTTP_204_NO_CONTENT)
async def reactivate_tenant_endpoint(
    tenant_id: str,
    db: DbSession,
    admin: PlatformAdmin,
) -> None:
    await service.reactivate_tenant(db, tenant_id, admin.id)


@router.post("/tenants/{tenant_id}/extend-trial", status_code=status.HTTP_204_NO_CONTENT)
async def extend_trial_endpoint(
    tenant_id: str,
    body: ExtendTrialRequest,
    db: DbSession,
    admin: PlatformAdmin,
) -> None:
    await service.extend_trial(db, tenant_id, admin.id, body.days)


@router.post("/tenants/{tenant_id}/impersonate")
async def start_impersonation_endpoint(
    tenant_id: str,
    db: DbSession,
    admin: PlatformAdmin,
) -> ImpersonateResponse:
    from app.config import get_settings
    from app.core.security import create_access_token
    from sqlalchemy import select

    from app.modules.tenants.models import Tenant

    imp = await service.start_impersonation(db, admin.id, tenant_id)
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one()
    settings = get_settings()
    access = create_access_token(
        {
            "sub": admin.id,
            "email": admin.email,
            "role": "administrator",
            "tenant_id": tenant_id,
            "is_platform_admin": True,
            "impersonating": True,
        }
    )
    return ImpersonateResponse(
        data={
            "impersonation_id": imp.id,
            "access_token": access,
            "tenant_id": tenant_id,
            "tenant_name": tenant.name,
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
        },
        message="Impersonation session started. This action is logged.",
    )


@router.delete("/tenants/{tenant_id}/impersonate", status_code=status.HTTP_204_NO_CONTENT)
async def end_impersonation_endpoint(
    tenant_id: str,
    db: DbSession,
    admin: PlatformAdmin,
) -> None:
    await service.end_impersonation(db, admin.id, tenant_id)


@router.get("/users")
async def list_platform_users(
    db: DbSession,
    _admin: PlatformAdmin,
    params: PageParams = Depends(),
) -> PlatformUsersResponse:
    data, meta = await service.list_platform_users(db, params)
    return PlatformUsersResponse(data=data, meta=meta)


@router.patch("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def patch_platform_user(
    user_id: str,
    body: UpdatePlatformUserRequest,
    db: DbSession,
    _admin: PlatformAdmin,
) -> None:
    await service.patch_platform_user(db, user_id, body)


@router.get("/health")
async def system_health(
    db: DbSession,
    _admin: PlatformAdmin,
) -> SystemHealthResponse:
    data = await service.get_system_health(db)
    return SystemHealthResponse(data=data)


@router.get("/engine-versions")
async def list_engine_versions_endpoint(
    db: DbSession,
    _admin: PlatformAdmin,
) -> EngineVersionListResponse:
    data = await service.list_engine_versions(db)
    return EngineVersionListResponse(data=data)


@router.post("/engine-versions/{version}/promote", status_code=status.HTTP_204_NO_CONTENT)
async def promote_engine_version_endpoint(
    version: str,
    db: DbSession,
    admin: PlatformAdmin,
) -> None:
    await service.promote_engine_version(db, version, admin.id)
