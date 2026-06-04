from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.modules.auth.models import User as _User

from app.core.enums import InvitationStatus, MemberStatus, UserRole
from app.core.exceptions import ECLException, InvalidCredentialsError
from app.core.hibp import validate_password_full
from app.core.security import generate_raw_token, hash_password, hash_token, new_ulid
from app.modules.auth.models import User
from app.modules.auth.schemas import AuthResponse
from app.modules.auth.service import _create_session_tokens, _get_active_user_by_email
from app.modules.invites.models import Invitation
from app.modules.invites.schemas import (
    AcceptInviteRequest,
    BatchInviteItem,
    BatchInviteOut,
    BatchInviteRequest,
    InviteValidateData,
    SendInviteRequest,
)
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

    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event
    from app.tasks.email_tasks import send_welcome_to_tenant_email  # noqa: PLC0415

    await log_event(db, AuditEvent.INVITE_ACCEPTED, user_id=user.id,
                    ip=ip, details={"tenant_id": inv.tenant_id})
    send_welcome_to_tenant_email.delay(user.id, inv.tenant_id)
    return auth


async def send_invite(
    db: AsyncSession,
    request: SendInviteRequest,
    inviter: "User",
) -> Invitation:
    if not inviter.is_email_verified:
        raise ECLException(
            "EMAIL_NOT_VERIFIED",
            "Please verify your email address before inviting team members.",
            403,
        )
    inviter_id = inviter.id
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

    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event
    from app.tasks.email_tasks import send_invite_email  # noqa: PLC0415

    await log_event(db, AuditEvent.INVITE_SENT, user_id=inviter.id,
                    details={"email": request.email, "role": request.role})
    send_invite_email.delay(inv.id, raw)
    return inv


async def batch_send_invites(
    db: AsyncSession,
    request: BatchInviteRequest,
    inviter: "User",
) -> list[BatchInviteOut]:
    if not inviter.is_email_verified:
        raise ECLException(
            "EMAIL_NOT_VERIFIED",
            "Please verify your email address before inviting team members.",
            403,
        )

    emails = [item.email for item in request.invites]
    if len(emails) != len(set(emails)):
        raise ECLException("DUPLICATE_EMAILS", "Duplicate email addresses in batch.", 400)

    for item in request.invites:
        if item.role not in {r.value for r in UserRole}:
            raise ECLException("VALIDATION_ERROR", f"Invalid role: {item.role}", 422, field="role")

    for item in request.invites:
        pending = await db.execute(
            select(Invitation).where(
                Invitation.email == item.email,
                Invitation.tenant_id == request.tenant_id,
                Invitation.status == InvitationStatus.PENDING.value,
            )
        )
        if pending.scalar_one_or_none():
            raise ECLException(
                "INVITE_ALREADY_PENDING",
                f"A pending invite already exists for {item.email}.",
                409,
            )
        existing_user = await _get_active_user_by_email(db, item.email)
        if existing_user:
            mem = await db.execute(
                select(TenantMembership).where(
                    TenantMembership.user_id == existing_user.id,
                    TenantMembership.tenant_id == request.tenant_id,
                    TenantMembership.status == MemberStatus.ACTIVE.value,
                )
            )
            if mem.scalar_one_or_none():
                raise ECLException(
                    "ALREADY_MEMBER", f"{item.email} is already a member.", 409
                )

    created: list[tuple[Invitation, str]] = []
    for item in request.invites:
        raw = generate_raw_token()
        inv = Invitation(
            id=new_ulid(),
            email=item.email,
            tenant_id=request.tenant_id,
            invited_by_user_id=inviter.id,
            role=item.role,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db.add(inv)
        created.append((inv, raw))

    await db.flush()

    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event
    from app.tasks.email_tasks import send_invite_email  # noqa: PLC0415

    for inv, raw in created:
        send_invite_email.delay(inv.id, raw)

    await log_event(
        db, AuditEvent.INVITE_BATCH_SENT, user_id=inviter.id,
        details={"count": len(created), "tenant_id": request.tenant_id},
    )
    return [BatchInviteOut(id=inv.id, email=inv.email, role=inv.role) for inv, _ in created]
