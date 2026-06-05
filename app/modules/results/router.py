from fastapi import APIRouter, Depends, Query

from app.dependencies import CurrentUser, DbSession, require_tenant_member
from app.modules.results import service
from app.modules.results.schemas import (
    DashboardResponse,
    LoanResponse,
    PortfolioResponse,
    SegmentResponse,
)
from app.modules.tenants.models import TenantMembership

router = APIRouter(prefix="/tenants", tags=["results"])


@router.get("/{tenant_id}/dashboard")
async def get_dashboard_endpoint(
    tenant_id: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
) -> DashboardResponse:
    data = await service.get_dashboard(db, tenant_id)
    return DashboardResponse(data=data)


@router.get("/{tenant_id}/results")
async def get_portfolio_endpoint(
    tenant_id: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
    run_id: str | None = Query(default=None),
) -> PortfolioResponse:
    data = await service.get_portfolio(db, tenant_id, run_id)
    return PortfolioResponse(data=data)


@router.get("/{tenant_id}/results/segments/{segment_name}")
async def get_segment_endpoint(
    tenant_id: str,
    segment_name: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
    run_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> SegmentResponse:
    data = await service.get_segment(
        db,
        tenant_id,
        segment_name,
        run_id=run_id,
        page=page,
        per_page=per_page,
    )
    return SegmentResponse(data=data)


@router.get("/{tenant_id}/results/loans/{loan_id}")
async def get_loan_endpoint(
    tenant_id: str,
    loan_id: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
    run_id: str | None = Query(default=None),
) -> LoanResponse:
    data = await service.get_loan(db, tenant_id, loan_id, run_id=run_id)
    return LoanResponse(data=data)
