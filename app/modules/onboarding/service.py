from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import InvitationStatus, UserRole
from app.core.exceptions import ECLException
from app.core.security import generate_raw_token, hash_token, new_ulid
from app.modules.collateral.models import CollateralType
from app.modules.invites.models import Invitation
from app.modules.onboarding.schemas import (
    CompleteOnboardingRequest,
    OnboardingCollateralOut,
    OnboardingSegmentOut,
    OnboardingStatusData,
    SaveProgressRequest,
)
from app.modules.segments.models import Segment
from app.modules.tenants.models import Tenant

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.modules.auth.models import User

_log = get_logger(__name__)

# Role normalisation: frontend sends title-case, DB stores lowercase
_ROLE_MAP: dict[str, str] = {r.title(): r.value for r in UserRole}


async def complete_onboarding(
    db: AsyncSession,
    tenant_id: str,
    user: User,
    req: CompleteOnboardingRequest,
) -> None:
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise ECLException("RESOURCE_NOT_FOUND", "Tenant not found.", 404)

    # 1. Update tenant profile
    tenant.name = req.profile.institution_name.strip()
    tenant.currency = req.profile.currency
    tenant.timezone = req.profile.timezone
    tenant.reporting_cadence = req.profile.cadence

    now = datetime.now(UTC)

    # 2. Replace segments (soft-delete existing, bulk-insert new)
    await db.execute(
        sa_update(Segment)
        .where(Segment.tenant_id == tenant_id, Segment.deleted_at.is_(None))
        .values(deleted_at=now)
    )
    for seg_in in req.segments:
        db.add(Segment(
            id=new_ulid(),
            tenant_id=tenant_id,
            name=seg_in.name.strip(),
            code=seg_in.code.strip().upper() if seg_in.code else None,
            created_by_user_id=user.id,
        ))

    # 3. Replace collateral types (soft-delete existing, bulk-insert new)
    await db.execute(
        sa_update(CollateralType)
        .where(CollateralType.tenant_id == tenant_id, CollateralType.deleted_at.is_(None))
        .values(deleted_at=now)
    )
    for col_in in req.collateral:
        db.add(CollateralType(
            id=new_ulid(),
            tenant_id=tenant_id,
            name=col_in.name.strip(),
            haircut=col_in.haircut,
            time_to_realize=col_in.ttr,
            created_by_user_id=user.id,
        ))

    # 4. Send invitations (bypass batch_send_invites to skip email-verification guard)
    if req.invites:
        _validate_invite_roles(req)
        invites_created: list[tuple[Invitation, str]] = []
        for inv_in in req.invites:
            role = _ROLE_MAP.get(inv_in.role, inv_in.role.lower())
            raw = generate_raw_token()
            inv = Invitation(
                id=new_ulid(),
                email=inv_in.email,
                tenant_id=tenant_id,
                invited_by_user_id=user.id,
                role=role,
                token_hash=hash_token(raw),
                status=InvitationStatus.PENDING.value,
                expires_at=now + timedelta(days=7),
            )
            db.add(inv)
            invites_created.append((inv, raw))

        await db.flush()

        from app.core.email_dispatch import queue_email_in_outbox
        from app.modules.audit.models import AuditEvent
        from app.modules.audit.service import log_event

        for inv, raw in invites_created:
            queue_email_in_outbox(
                db,
                task_name="send_invite_email",
                payload={"invitation_id": inv.id, "raw_token": raw},
            )

        await log_event(
            db,
            AuditEvent.INVITE_BATCH_SENT,
            user_id=user.id,
            details={"count": len(invites_created), "tenant_id": tenant_id},
        )

    # 5. Mark onboarding complete
    tenant.onboarding_completed_at = now
    tenant.onboarding_progress = None

    # 6. Send welcome email to the admin who completed onboarding
    from app.core.email_dispatch import queue_email_in_outbox

    queue_email_in_outbox(
        db,
        task_name="send_welcome_email",
        payload={"user_id": user.id, "tenant_id": tenant_id},
    )

    # 7. Audit
    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event

    await log_event(
        db,
        AuditEvent.ONBOARDING_COMPLETED,
        user_id=user.id,
        details={"tenant_id": tenant_id},
    )


def _validate_invite_roles(req: CompleteOnboardingRequest) -> None:
    valid = {r.value for r in UserRole}
    for inv_in in req.invites:
        normalised = _ROLE_MAP.get(inv_in.role, inv_in.role.lower())
        if normalised not in valid:
            raise ECLException(
                "VALIDATION_ERROR", f"Invalid role: {inv_in.role}", 422, field="role"
            )


async def save_progress(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    req: SaveProgressRequest,
) -> None:
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise ECLException("RESOURCE_NOT_FOUND", "Tenant not found.", 404)

    tenant.onboarding_progress = req.progress

    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event

    await log_event(
        db,
        AuditEvent.ONBOARDING_PROGRESS_SAVED,
        user_id=user_id,
        details={"tenant_id": tenant_id},
    )


async def get_status(db: AsyncSession, tenant_id: str) -> OnboardingStatusData:
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise ECLException("RESOURCE_NOT_FOUND", "Tenant not found.", 404)

    segs_result = await db.execute(
        select(Segment)
        .where(Segment.tenant_id == tenant_id, Segment.deleted_at.is_(None))
        .order_by(Segment.name)
    )
    segments = [
        OnboardingSegmentOut(id=s.id, name=s.name, code=s.code)
        for s in segs_result.scalars().all()
    ]

    cols_result = await db.execute(
        select(CollateralType)
        .where(CollateralType.tenant_id == tenant_id, CollateralType.deleted_at.is_(None))
        .order_by(CollateralType.name)
    )
    collateral_types = [
        OnboardingCollateralOut(
            id=c.id,
            name=c.name,
            haircut=c.haircut,
            time_to_realize=c.time_to_realize,
        )
        for c in cols_result.scalars().all()
    ]

    return OnboardingStatusData(
        is_complete=tenant.onboarding_completed_at is not None,
        completed_at=tenant.onboarding_completed_at,
        progress=tenant.onboarding_progress,
        segments=segments,
        collateral_types=collateral_types,
    )
