from fastapi import APIRouter, Depends, status

from app.dependencies import CurrentUser, DbSession, require_tenant_admin, require_tenant_member
from app.modules.onboarding import service
from app.modules.onboarding.schemas import (
    CompleteOnboardingRequest,
    OnboardingCompleteResponse,
    OnboardingStatusResponse,
    SaveProgressRequest,
    SaveProgressResponse,
)
from app.modules.tenants.models import TenantMembership

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post(
    "/{tenant_id}/complete",
    status_code=status.HTTP_200_OK,
    response_model=OnboardingCompleteResponse,
)
async def complete_onboarding_endpoint(
    tenant_id: str,
    body: CompleteOnboardingRequest,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),  # noqa: B008
) -> OnboardingCompleteResponse:
    await service.complete_onboarding(db, tenant_id, user, body)
    return OnboardingCompleteResponse(
        data={"message": "Onboarding complete."},
        message="Workspace setup complete.",
    )


@router.post(
    "/{tenant_id}/save-progress",
    status_code=status.HTTP_200_OK,
    response_model=SaveProgressResponse,
)
async def save_progress_endpoint(
    tenant_id: str,
    body: SaveProgressRequest,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),  # noqa: B008
) -> SaveProgressResponse:
    await service.save_progress(db, tenant_id, user.id, body)
    return SaveProgressResponse(
        data={"message": "Progress saved."},
        message="Progress saved.",
    )


@router.get(
    "/{tenant_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=OnboardingStatusResponse,
)
async def get_onboarding_status_endpoint(
    tenant_id: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),  # noqa: B008
) -> OnboardingStatusResponse:
    data = await service.get_status(db, tenant_id)
    return OnboardingStatusResponse(data=data)
