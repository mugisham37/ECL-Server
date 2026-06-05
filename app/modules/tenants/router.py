from fastapi import APIRouter, Depends, status

from app.core.pagination import PageParams
from app.dependencies import CurrentUser, DbSession, require_tenant_admin, require_tenant_member
from app.modules.tenants.models import TenantMembership
from app.modules.invites.schemas import InviteListResponse
from app.modules.invites import service as invites_service
from app.modules.tenants.schemas import (
    CloseTenantRequest,
    MembersListResponse,
    TenantResponse,
    UpdateMemberRequest,
    UpdateTenantRequest,
)
from app.modules.tenants import service

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/{tenant_id}")
async def get_tenant_endpoint(
    tenant_id: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
) -> TenantResponse:
    data = await service.get_tenant(db, tenant_id)
    return TenantResponse(data=data)


@router.patch("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def patch_tenant(
    tenant_id: str,
    body: UpdateTenantRequest,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),
) -> None:
    await service.update_tenant(db, tenant_id, body)


@router.get("/{tenant_id}/members")
async def list_members_endpoint(
    tenant_id: str,
    db: DbSession,
    user: CurrentUser,
    params: PageParams = Depends(),
    _m: TenantMembership = Depends(require_tenant_member),
) -> MembersListResponse:
    page = await service.list_members(db, tenant_id, params, user.id)
    return MembersListResponse(data=page.data, meta=page.meta)


@router.patch("/{tenant_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def patch_member(
    tenant_id: str,
    user_id: str,
    body: UpdateMemberRequest,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),
) -> None:
    await service.update_member(db, tenant_id, user_id, body, user.id)


@router.delete("/{tenant_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    tenant_id: str,
    user_id: str,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),
) -> None:
    await service.remove_member(db, tenant_id, user_id, user.id)


@router.get("/{tenant_id}/invites")
async def list_tenant_invites_endpoint(
    tenant_id: str,
    db: DbSession,
    user: CurrentUser,
    status: str = "pending",
    _a: TenantMembership = Depends(require_tenant_admin),
) -> InviteListResponse:
    data = await invites_service.list_tenant_invites(db, tenant_id, status)
    return InviteListResponse(data=data)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_tenant_endpoint(
    tenant_id: str,
    body: CloseTenantRequest,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),
) -> None:
    await service.close_tenant(db, tenant_id, user.id, body.confirmation)
