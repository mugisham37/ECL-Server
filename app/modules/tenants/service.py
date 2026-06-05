from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MemberStatus, TenantStatus, UserRole
from app.core.exceptions import (
    AlreadySuspendedError,
    ECLException,
    InvalidConfirmationError,
    LastAdminError,
)
from app.core.pagination import Page, PageMeta, PageParams
from app.modules.auth.models import User
from app.modules.auth.utils import user_initials
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import log_event
from app.modules.sessions.models import Session
from app.modules.tenants.models import Tenant, TenantMembership
from app.modules.tenants.schemas import MemberOut, TenantOut, UpdateMemberRequest, UpdateTenantRequest


async def get_tenant(db: AsyncSession, tenant_id: str) -> TenantOut:
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    )
    t = result.scalar_one_or_none()
    if not t:
        raise ECLException("RESOURCE_NOT_FOUND", "Tenant not found.", 404)
    return TenantOut(
        id=t.id,
        name=t.name,
        slug=t.slug,
        plan=t.plan,
        status=t.status,
        currency=t.currency,
        reporting_cadence=t.reporting_cadence,
        timezone=t.timezone,
        close_requested_at=t.close_requested_at,
    )


async def update_tenant(db: AsyncSession, tenant_id: str, body: UpdateTenantRequest) -> None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    t = result.scalar_one_or_none()
    if not t:
        raise ECLException("RESOURCE_NOT_FOUND", "Tenant not found.", 404)
    if body.name:
        t.name = body.name
    if body.currency:
        t.currency = body.currency
    if body.reporting_cadence:
        t.reporting_cadence = body.reporting_cadence
    if body.timezone:
        t.timezone = body.timezone


async def assert_not_last_admin(db: AsyncSession, tenant_id: str, user_id: str) -> None:
    """Raises LastAdminError if removing/demoting this user would leave zero active administrators."""
    result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m or m.role != UserRole.ADMINISTRATOR.value:
        return

    admins = await db.execute(
        select(func.count())
        .select_from(TenantMembership)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.role == UserRole.ADMINISTRATOR.value,
            TenantMembership.status == MemberStatus.ACTIVE.value,
            TenantMembership.user_id != user_id,
        )
    )
    if admins.scalar_one() == 0:
        raise LastAdminError()


async def list_members(
    db: AsyncSession,
    tenant_id: str,
    params: PageParams,
    current_user_id: str,
) -> Page[MemberOut]:
    last_active_subq = (
        select(func.max(Session.last_active_at))
        .where(Session.user_id == TenantMembership.user_id)
        .correlate(TenantMembership)
        .scalar_subquery()
    )

    base = (
        select(TenantMembership, User, last_active_subq.label("last_active_at"))
        .join(User, User.id == TenantMembership.user_id)
        .where(
            TenantMembership.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
        .order_by(User.name)
    )
    count_q = select(func.count()).select_from(
        select(TenantMembership.id)
        .where(TenantMembership.tenant_id == tenant_id)
        .subquery()
    )
    total = (await db.execute(count_q)).scalar_one()
    offset = (params.page - 1) * params.per_page
    result = await db.execute(base.offset(offset).limit(params.per_page))
    rows = result.all()
    data = [
        MemberOut(
            id=u.id,
            name=u.name,
            email=u.email,
            initials=user_initials(u.name),
            role=m.role,
            status=m.status,
            last_active_at=last_active,
            is_you=u.id == current_user_id,
        )
        for m, u, last_active in rows
    ]
    pages = max(1, (total + params.per_page - 1) // params.per_page)
    return Page(
        data=data,
        meta=PageMeta(
            total=total,
            page=params.page,
            per_page=params.per_page,
            pages=pages,
            has_next=params.page < pages,
            has_prev=params.page > 1,
        ),
    )


async def update_member(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    body: UpdateMemberRequest,
    actor_id: str,
) -> None:
    if user_id == actor_id and body.status == MemberStatus.DISABLED.value:
        raise ECLException("VALIDATION_ERROR", "Cannot disable your own account.", 400)

    result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise ECLException("RESOURCE_NOT_FOUND", "Member not found.", 404)

    demoting_admin = (
        m.role == UserRole.ADMINISTRATOR.value
        and body.role is not None
        and body.role != UserRole.ADMINISTRATOR.value
    )
    disabling_admin = (
        m.role == UserRole.ADMINISTRATOR.value
        and body.status == MemberStatus.DISABLED.value
    )
    if demoting_admin or disabling_admin:
        await assert_not_last_admin(db, tenant_id, user_id)

    if body.role:
        m.role = body.role
    if body.status:
        m.status = body.status


async def remove_member(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    actor_id: str,
) -> None:
    if user_id == actor_id:
        raise ECLException("VALIDATION_ERROR", "Cannot remove yourself.", 400)
    result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise ECLException("RESOURCE_NOT_FOUND", "Member not found.", 404)
    if m.role == UserRole.ADMINISTRATOR.value:
        await assert_not_last_admin(db, tenant_id, user_id)
    await db.delete(m)


async def close_tenant(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    confirmation: str,
) -> None:
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise ECLException("RESOURCE_NOT_FOUND", "Tenant not found.", 404)

    if confirmation.strip() != "CLOSE":
        raise InvalidConfirmationError(expected="CLOSE")

    if tenant.status == TenantStatus.CLOSING.value:
        raise AlreadySuspendedError()

    tenant.close_requested_at = datetime.now(UTC)
    tenant.close_requested_by = user_id
    tenant.status = TenantStatus.CLOSING.value
    await db.flush()

    await log_event(
        db,
        AuditEvent.TENANT_CLOSE_REQUESTED,
        user_id=user_id,
        tenant_id=tenant_id,
        details={"requested_by_user_id": user_id, "tenant_id": tenant_id},
    )
    await log_event(
        db,
        AuditEvent.TENANT_CLOSE_REQUESTED,
        user_id=user_id,
        tenant_id=None,
        details={"requested_by_user_id": user_id, "tenant_id": tenant_id},
    )
