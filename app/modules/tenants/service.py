from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MemberStatus, UserRole
from app.core.exceptions import ECLException
from app.core.pagination import Page, PageParams, paginate
from app.modules.auth.models import User
from app.modules.auth.utils import user_initials
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


async def list_members(
    db: AsyncSession,
    tenant_id: str,
    params: PageParams,
    current_user_id: str,
) -> Page[MemberOut]:
    base = (
        select(TenantMembership, User)
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
            last_active=u.last_login_at,
            is_you=u.id == current_user_id,
        )
        for m, u in rows
    ]
    pages = max(1, (total + params.per_page - 1) // params.per_page)
    from app.core.pagination import PageMeta

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

    if body.role == UserRole.ADMINISTRATOR.value or m.role == UserRole.ADMINISTRATOR.value:
        admins = await db.execute(
            select(func.count())
            .select_from(TenantMembership)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.role == UserRole.ADMINISTRATOR.value,
                TenantMembership.status == MemberStatus.ACTIVE.value,
            )
        )
        admin_count = admins.scalar_one()
        if m.role == UserRole.ADMINISTRATOR.value and admin_count <= 1 and body.role != UserRole.ADMINISTRATOR.value:
            raise ECLException(
                "VALIDATION_ERROR",
                "Cannot demote the last administrator.",
                400,
            )

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
        admins = await db.execute(
            select(func.count())
            .select_from(TenantMembership)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.role == UserRole.ADMINISTRATOR.value,
                TenantMembership.status == MemberStatus.ACTIVE.value,
            )
        )
        if admins.scalar_one() <= 1:
            raise ECLException(
                "VALIDATION_ERROR",
                "Cannot remove the last administrator.",
                400,
            )
    await db.delete(m)
