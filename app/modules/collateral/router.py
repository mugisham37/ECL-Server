from fastapi import APIRouter, Depends, status

from app.dependencies import CurrentUser, DbSession, require_tenant_admin, require_tenant_member
from app.modules.tenants.models import TenantMembership
from app.modules.collateral.schemas import (
    BatchCreateCollateralTypesRequest,
    CollateralTypeListResponse,
    CollateralTypeResponse,
    CreateCollateralTypeRequest,
    UpdateCollateralTypeRequest,
)
from app.modules.collateral import service

router = APIRouter(prefix="/tenants", tags=["collateral"])


@router.get("/{tenant_id}/collateral-types")
async def list_collateral_types_endpoint(
    tenant_id: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
) -> CollateralTypeListResponse:
    data = await service.list_collateral_types(db, tenant_id)
    return CollateralTypeListResponse(data=data)


@router.post("/{tenant_id}/collateral-types", status_code=status.HTTP_201_CREATED)
async def create_collateral_type_endpoint(
    tenant_id: str,
    body: CreateCollateralTypeRequest,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),
) -> CollateralTypeResponse:
    data = await service.create_collateral_type(db, tenant_id, user.id, body)
    return CollateralTypeResponse(data=data)


@router.post("/{tenant_id}/collateral-types/batch", status_code=status.HTTP_201_CREATED)
async def batch_create_collateral_types_endpoint(
    tenant_id: str,
    body: BatchCreateCollateralTypesRequest,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),
) -> CollateralTypeListResponse:
    data = await service.batch_create_collateral_types(db, tenant_id, user.id, body)
    return CollateralTypeListResponse(data=data)


@router.patch(
    "/{tenant_id}/collateral-types/{collateral_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def update_collateral_type_endpoint(
    tenant_id: str,
    collateral_id: str,
    body: UpdateCollateralTypeRequest,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),
) -> None:
    await service.update_collateral_type(db, tenant_id, collateral_id, body)


@router.delete(
    "/{tenant_id}/collateral-types/{collateral_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_collateral_type_endpoint(
    tenant_id: str,
    collateral_id: str,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),
) -> None:
    await service.delete_collateral_type(db, tenant_id, collateral_id)
