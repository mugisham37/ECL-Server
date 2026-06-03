from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import InvitationStatus, MemberStatus, UserRole
from app.core.exceptions import ECLException, InvalidCredentialsError
from app.core.hibp import validate_password_full
from app.core.security import generate_raw_token, hash_password, hash_token, new_ulid
from app.modules.auth.models import User
from app.modules.auth.schemas import AuthResponse
from app.modules.auth.service import _create_session_tokens, _get_active_user_by_email
from app.modules.invites.models import Invitation
from app.modules.invites.schemas import AcceptInviteRequest, InviteValidateData, SendInviteRequest
from app.modules.tenants.models import Tenant, TenantMembership


async def validate_invite(db: AsyncSession, raw_token: str) -> InviteValidateData:
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(Invitation, Tenant, User)
        .join(Tenant, Tenant.id == Invitation.tenant_id)
        .join(User, User.id == Invitation.invited_by_user_id)
        .where(Invitation.token_hash == token_hash)
    )
    row = result.first()
    if not row:
        raise ECLException("INVALID_INVITE_TOKEN", "Invite link is invalid or expired.", 400)
    inv, tenant, inviter = row
    if inv.status != InvitationStatus.PENDING.value or inv.expires_at < datetime.now(UTC):
        raise ECLException("INVALID_INVITE_TOKEN", "Invite link is invalid or expired.", 400)
    return InviteValidateData(
        email=inv.email,
        tenant_name=tenant.name,
        inviter_name=inviter.name,
        role=inv.role,
        expires_at=inv.expires_at,
    )


async def accept_invite(
    db: AsyncSession,
    request: AcceptInviteRequest,
    ip: str,
    user_agent: str | None,
    response: Response,
) -> AuthResponse:
    token_hash = hash_token(request.token)
    result = await db.execute(
        select(Invitation).where(Invitation.token_hash == token_hash)
    )
    inv = result.scalar_one_or_none()
    if not inv or inv.status != InvitationStatus.PENDING.value:
        raise ECLException("INVALID_INVITE_TOKEN", "Invite link is invalid or expired.", 400)
    if inv.expires_at < datetime.now(UTC):
        raise ECLException("INVALID_INVITE_TOKEN", "Invite link has expired.", 400)

    violations = await validate_password_full(request.password, name=request.name)
    if violations:
        from app.modules.auth.service import _violation_detail

        raise ECLException(violations[0], _violation_detail(violations[0]), 422, field="password")

    user = await _get_active_user_by_email(db, inv.email)
    if user:
        from app.core.security import verify_password

        if not verify_password(request.password, user.hashed_password):
            raise InvalidCredentialsError()
    else:
        user = User(
            id=new_ulid(),
            email=inv.email.lower(),
            name=request.name.strip(),
            hashed_password=hash_password(request.password),
            is_email_verified=True,
        )
        db.add(user)

    existing = await db.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == inv.tenant_id,
            TenantMembership.status == MemberStatus.ACTIVE.value,
        )
    )
    if existing.scalar_one_or_none():
        raise ECLException("ALREADY_MEMBER", "Already a member of this workspace.", 409)

    membership = TenantMembership(
        id=new_ulid(),
        user_id=user.id,
        tenant_id=inv.tenant_id,
        role=inv.role,
        status=MemberStatus.ACTIVE.value,
    )
    db.add(membership)
    inv.status = InvitationStatus.ACCEPTED.value
    inv.accepted_at = datetime.now(UTC)

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == inv.tenant_id))
    tenant = tenant_result.scalar_one()

    auth = await _create_session_tokens(
        db, user, membership, tenant, remember=True, ip=ip, user_agent=user_agent, response=response
    )
    auth.message = "Invite accepted"
    return auth


async def send_invite(
    db: AsyncSession,
    request: SendInviteRequest,
    inviter_id: str,
) -> Invitation:
    pending = await db.execute(
        select(Invitation).where(
            Invitation.email == request.email,
            Invitation.tenant_id == request.tenant_id,
            Invitation.status == InvitationStatus.PENDING.value,
        )
    )
    if pending.scalar_one_or_none():
        raise ECLException(
            "INVITE_ALREADY_PENDING",
            "A pending invite already exists for this email.",
            409,
        )

    existing_user = await _get_active_user_by_email(db, request.email)
    if existing_user:
        mem = await db.execute(
            select(TenantMembership).where(
                TenantMembership.user_id == existing_user.id,
                TenantMembership.tenant_id == request.tenant_id,
                TenantMembership.status == MemberStatus.ACTIVE.value,
            )
        )
        if mem.scalar_one_or_none():
            raise ECLException("ALREADY_MEMBER", "User is already a member.", 409)

    if request.role not in {r.value for r in UserRole}:
        raise ECLException("VALIDATION_ERROR", "Invalid role.", 422, field="role")

    raw = generate_raw_token()
    inv = Invitation(
        id=new_ulid(),
        email=request.email,
        tenant_id=request.tenant_id,
        invited_by_user_id=inviter_id,
        role=request.role,
        token_hash=hash_token(raw),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(inv)
    await db.flush()
    inv._raw_token = raw  # type: ignore[attr-defined]
    return inv
