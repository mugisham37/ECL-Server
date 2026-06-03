from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.hibp import validate_password_full
from app.core.security import hash_password, verify_password
from app.core.exceptions import ECLException
from app.modules.auth.models import User
from app.modules.auth.utils import user_initials
from app.modules.sessions.models import RefreshToken, Session
from app.modules.sessions.schemas import (
    ChangePasswordRequest,
    MeData,
    MembershipOut,
    SessionOut,
    UpdateProfileRequest,
    UserProfileOut,
)
from app.modules.tenants.models import Tenant, TenantMembership


async def get_me(db: AsyncSession, user: User, tenant_id: str | None) -> MeData:
    memberships_result = await db.execute(
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == user.id, Tenant.deleted_at.is_(None))
    )
    memberships: list[MembershipOut] = []
    active_role = ""
    active_tenant_name = ""
    active_tenant_id = tenant_id or ""
    for m, t in memberships_result.all():
        memberships.append(
            MembershipOut(
                tenant_id=t.id,
                tenant_name=t.name,
                role=m.role,
                status=m.status,
            )
        )
        if t.id == tenant_id or (not tenant_id and m.status == "active"):
            active_role = m.role
            active_tenant_name = t.name
            active_tenant_id = t.id

    if not active_tenant_id and memberships:
        active_tenant_id = memberships[0].tenant_id
        active_tenant_name = memberships[0].tenant_name
        active_role = memberships[0].role

    return MeData(
        user=UserProfileOut(
            id=user.id,
            name=user.name,
            email=user.email,
            role=active_role,
            tenant_id=active_tenant_id,
            tenant_name=active_tenant_name,
            is_email_verified=user.is_email_verified,
            initials=user_initials(user.name),
        ),
        memberships=memberships,
    )


async def update_profile(db: AsyncSession, user: User, body: UpdateProfileRequest) -> None:
    if body.name:
        user.name = body.name.strip()


async def change_password(db: AsyncSession, user: User, body: ChangePasswordRequest) -> None:
    if not verify_password(body.current_password, user.hashed_password):
        raise ECLException("INVALID_CREDENTIALS", "Current password is incorrect.", 401)
    violations = await validate_password_full(body.new_password, name=user.name)
    if violations:
        from app.modules.auth.service import _violation_detail

        raise ECLException(violations[0], _violation_detail(violations[0]), 422, field="new_password")
    user.hashed_password = hash_password(body.new_password)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.is_revoked.is_(False))
    )
    tokens = list(result.scalars().all())
    if len(tokens) > 1:
        for rt in tokens[1:]:
            rt.is_revoked = True


async def list_sessions(db: AsyncSession, user_id: str, current_rt_id: str | None) -> list[SessionOut]:
    result = await db.execute(
        select(Session).where(Session.user_id == user_id).order_by(Session.last_active_at.desc())
    )
    return [
        SessionOut(
            id=s.id,
            device_type=s.device_type,
            device_name=s.device_name,
            last_active_at=s.last_active_at,
            current=s.refresh_token_id == current_rt_id if current_rt_id else False,
        )
        for s in result.scalars().all()
    ]


async def revoke_session(db: AsyncSession, user_id: str, session_id: str, current_session_id: str | None) -> None:
    if session_id == current_session_id:
        raise ECLException(
            "VALIDATION_ERROR",
            "Cannot revoke current session. Use logout instead.",
            400,
        )
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    sess = result.scalar_one_or_none()
    if not sess:
        raise ECLException("RESOURCE_NOT_FOUND", "Session not found.", 404)
    rt_result = await db.execute(select(RefreshToken).where(RefreshToken.id == sess.refresh_token_id))
    rt = rt_result.scalar_one_or_none()
    if rt:
        rt.is_revoked = True
    await db.execute(delete(Session).where(Session.id == session_id))


async def revoke_other_sessions(db: AsyncSession, user_id: str, current_session_id: str | None) -> int:
    result = await db.execute(select(Session).where(Session.user_id == user_id))
    count = 0
    for sess in result.scalars().all():
        if sess.id == current_session_id:
            continue
        rt_result = await db.execute(select(RefreshToken).where(RefreshToken.id == sess.refresh_token_id))
        rt = rt_result.scalar_one_or_none()
        if rt:
            rt.is_revoked = True
        await db.delete(sess)
        count += 1
    return count
