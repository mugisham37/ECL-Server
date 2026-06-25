from datetime import UTC, datetime, timedelta

from fastapi import Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.enums import MemberStatus, TenantStatus, UserRole
from app.core.exceptions import (
    AccountDisabledError,
    AccountLockedError,
    ECLException,
    EmailTakenError,
    InvalidCredentialsError,
    SlugTakenError,
)
from app.core.hibp import validate_password_full
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_raw_token,
    hash_password,
    hash_token,
    new_ulid,
    verify_password_or_dummy,
)
from app.modules.auth.models import EmailVerificationToken, PasswordResetToken, User
from app.modules.auth.schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MFAChallengeResponse,
    MFAVerifyRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SwitchTenantData,
    SwitchTenantRequest,
    TokenData,
    UserOut,
)
from app.modules.auth.utils import hash_ip, parse_device, unique_slug, user_initials
from app.core.logging import get_logger
from app.modules.sessions.models import RefreshToken, Session
from app.modules.tenants.models import Tenant, TenantMembership

_log = get_logger(__name__)


def _refresh_expiry(remember: bool, settings: Settings) -> datetime:
    if remember:
        days = settings.jwt_refresh_token_expire_days
    else:
        days = 1
    return datetime.now(UTC) + timedelta(days=days)


def _set_refresh_cookie(response: Response, raw_token: str, expires: datetime) -> None:
    settings = get_settings()
    max_age = int((expires - datetime.now(UTC)).total_seconds())
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=max_age,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/api/v1/auth",
    )


async def _get_active_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(
            User.email == email.lower(),
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _get_membership(
    session: AsyncSession, user_id: str, tenant_id: str | None = None
) -> tuple[TenantMembership, Tenant] | None:
    q = (
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(
            TenantMembership.user_id == user_id,
            TenantMembership.status == MemberStatus.ACTIVE.value,
            Tenant.deleted_at.is_(None),
        )
    )
    if tenant_id:
        q = q.where(TenantMembership.tenant_id == tenant_id)
    else:
        q = q.order_by(TenantMembership.joined_at.desc())
    result = await session.execute(q)
    row = result.first()
    if not row:
        return None
    return row[0], row[1]


def _user_out(user: User, membership: TenantMembership, tenant: Tenant) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=membership.role,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        currency=tenant.currency or "USD",
        is_email_verified=user.is_email_verified,
        is_onboarding_complete=tenant.onboarding_completed_at is not None,
        is_platform_admin=user.is_platform_admin,
    )


async def _create_session_tokens(
    session: AsyncSession,
    user: User,
    membership: TenantMembership,
    tenant: Tenant,
    remember: bool,
    ip: str,
    user_agent: str | None,
    response: Response | None = None,
) -> AuthResponse:
    settings = get_settings()
    family_id = new_ulid()
    raw_refresh = generate_raw_token()
    expires = _refresh_expiry(remember, settings)

    rt = RefreshToken(
        id=new_ulid(),
        user_id=user.id,
        token_family_id=family_id,
        token_hash=hash_token(raw_refresh),
        expires_at=expires,
    )
    session.add(rt)

    device_type, device_name, browser = parse_device(user_agent)
    sess = Session(
        id=new_ulid(),
        user_id=user.id,
        refresh_token_id=rt.id,
        device_type=device_type,
        device_name=device_name,
        browser=browser,
        ip_address_hash=hash_ip(ip, settings.secret_key),
    )
    session.add(sess)

    access = create_access_token(
        {
            "sub": user.id,
            "email": user.email,
            "name": user.name,
            "role": membership.role,
            "tenant_id": tenant.id,
            "is_platform_admin": user.is_platform_admin,
        }
    )

    if response is not None:
        _set_refresh_cookie(response, raw_refresh, expires)

    return AuthResponse(
        data=TokenData(
            access_token=access,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=_user_out(user, membership, tenant),
        ),
        message="Login successful",
    )


async def check_lockout(user: User) -> None:
    if user.locked_until and user.locked_until > datetime.now(UTC):
        retry = int((user.locked_until - datetime.now(UTC)).total_seconds())
        _log.warning("account_locked", user_id=user.id, retry_after=max(retry, 1))
        raise AccountLockedError(max(retry, 1))


async def handle_failed_login(session: AsyncSession, user: User) -> None:
    settings = get_settings()
    user.failed_login_count += 1
    count = user.failed_login_count
    now = datetime.now(UTC)
    if count >= settings.lockout_threshold_3:
        user.locked_until = now + timedelta(hours=24)
    elif count >= settings.lockout_threshold_2:
        user.locked_until = now + timedelta(hours=1)
    elif count >= settings.lockout_threshold_1:
        user.locked_until = now + timedelta(minutes=15)
    await session.flush()


async def register_user(
    db: AsyncSession,
    request: RegisterRequest,
    ip: str,
    user_agent: str | None,
    response: Response,
) -> AuthResponse:
    violations = await validate_password_full(
        request.password, name=request.name, org_name=request.company_name
    )
    if violations:
        code = violations[0]
        raise ECLException(code, _violation_detail(code), 422, field="password")

    existing = await _get_active_user_by_email(db, request.email)
    if existing:
        raise EmailTakenError()

    slugs_result = await db.execute(
        select(Tenant.slug).where(Tenant.deleted_at.is_(None))
    )
    existing_slugs = {r[0] for r in slugs_result.all()}
    slug = await unique_slug(request.company_name, existing_slugs)

    user = User(
        id=new_ulid(),
        email=request.email.lower(),
        name=request.name.strip(),
        hashed_password=hash_password(request.password),
        is_active=True,
        is_email_verified=False,
        is_platform_admin=False,
        failed_login_count=0,
    )
    tenant = Tenant(
        id=new_ulid(),
        name=request.company_name.strip(),
        slug=slug,
        status=TenantStatus.TRIAL.value,
    )
    membership = TenantMembership(
        id=new_ulid(),
        user_id=user.id,
        tenant_id=tenant.id,
        role=UserRole.ADMINISTRATOR.value,
        status=MemberStatus.ACTIVE.value,
    )
    db.add_all([user, tenant, membership])

    raw_verify = generate_raw_token(32)
    db.add(
        EmailVerificationToken(
            id=new_ulid(),
            user_id=user.id,
            token_hash=hash_token(raw_verify),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )

    auth_resp = await _create_session_tokens(
        db, user, membership, tenant, remember=True, ip=ip, user_agent=user_agent, response=response
    )
    auth_resp.message = "Registration successful"

    from app.core.email_dispatch import queue_email_in_outbox
    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event

    await log_event(db, AuditEvent.USER_REGISTER, user_id=user.id, ip=ip, user_agent=user_agent)
    queue_email_in_outbox(
        db,
        task_name="send_verification_email",
        payload={"user_id": user.id, "raw_token": raw_verify},
    )
    return auth_resp


async def login_user(
    db: AsyncSession,
    request: LoginRequest,
    ip: str,
    user_agent: str | None,
    response: Response,
) -> AuthResponse:
    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event

    user = await _get_active_user_by_email(db, request.email)
    valid = verify_password_or_dummy(
        request.password, user.hashed_password if user else None
    )
    if not user or not valid:
        if user:
            await check_lockout(user)
            await handle_failed_login(db, user)
            await log_event(
                db, AuditEvent.LOGIN_FAILED,
                user_id=user.id, status="failure",
                error_code="INVALID_CREDENTIALS", ip=ip, user_agent=user_agent,
            )
            _log.warning(
                "login_failed",
                email_domain=request.email.split("@")[-1],
                failed_count=user.failed_login_count,
            )
        raise InvalidCredentialsError()

    await check_lockout(user)
    if not user.is_active:
        raise AccountDisabledError()

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)

    membership_row = await _get_membership(db, user.id)
    if not membership_row:
        raise ECLException("NOT_TENANT_MEMBER", "No active workspace membership.", 403)
    membership, tenant = membership_row

    if user.totp_enabled:
        from app.core.security import create_mfa_challenge_token

        challenge = create_mfa_challenge_token(user.id)
        return MFAChallengeResponse(challenge_token=challenge)

    resp = await _create_session_tokens(
        db,
        user,
        membership,
        tenant,
        remember=request.remember,
        ip=ip,
        user_agent=user_agent,
        response=response,
    )
    await log_event(db, AuditEvent.LOGIN_SUCCESS, user_id=user.id, ip=ip, user_agent=user_agent)
    _log.info("login_success", user_id=user.id, tenant_id=tenant.id)
    return resp


async def verify_mfa(
    db: AsyncSession,
    redis: Redis,
    request: MFAVerifyRequest,
    ip: str,
    user_agent: str | None,
    response: Response,
) -> AuthResponse:
    import pyotp

    from app.core.cache import blacklist_token, is_token_blacklisted
    from app.core.security import decrypt_totp_secret
    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event

    try:
        payload = decode_access_token(request.challenge_token)
    except ECLException:
        raise ECLException("INVALID_CHALLENGE_TOKEN", "Invalid or expired MFA challenge.", 400)

    if payload.get("type") != "mfa_challenge":
        raise ECLException("INVALID_CHALLENGE_TOKEN", "Invalid token type.", 400)

    jti = payload.get("jti", "")
    if jti and await is_token_blacklisted(redis, jti, db):
        raise ECLException("INVALID_CHALLENGE_TOKEN", "MFA challenge already used.", 400)

    user_result = await db.execute(
        select(User).where(User.id == payload["sub"], User.deleted_at.is_(None))
    )
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise ECLException("ACCOUNT_DISABLED", "Account is disabled.", 403)

    code = request.code

    if len(code) == 8:
        matched = None
        for entry in (user.totp_backup_codes or []):
            if not entry.get("used"):
                try:
                    from argon2 import PasswordHasher
                    from argon2.exceptions import VerifyMismatchError

                    ph = PasswordHasher()
                    ph.verify(entry["hash"], code)
                    matched = entry
                    break
                except VerifyMismatchError:
                    pass
        if not matched:
            await log_event(db, AuditEvent.TOTP_FAILED, user_id=user.id, ip=ip,
                            status="failure", error_code="INVALID_RECOVERY_CODE")
            raise ECLException("INVALID_TOTP_CODE", "Invalid recovery code.", 400)
        matched["used"] = True
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(user, "totp_backup_codes")
        await log_event(db, AuditEvent.RECOVERY_CODE_USED, user_id=user.id, ip=ip)
    else:
        if not user.totp_secret_encrypted:
            raise ECLException("TOTP_NOT_ENABLED", "MFA is not configured.", 400)
        secret = decrypt_totp_secret(user.totp_secret_encrypted)
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            await log_event(db, AuditEvent.TOTP_FAILED, user_id=user.id, ip=ip,
                            status="failure", error_code="INVALID_TOTP_CODE")
            raise ECLException("INVALID_TOTP_CODE", "Invalid TOTP code.", 400)
        await log_event(db, AuditEvent.TOTP_VERIFIED, user_id=user.id, ip=ip)

    if jti:
        from datetime import UTC, datetime

        expires_at = datetime.fromtimestamp(int(payload["exp"]), UTC)
        await blacklist_token(redis, db, jti, user.id, expires_at, "mfa_challenge_used")

    membership_row = await _get_membership(db, user.id)
    if not membership_row:
        raise ECLException("NOT_TENANT_MEMBER", "No active workspace membership.", 403)
    membership, tenant = membership_row

    resp = await _create_session_tokens(
        db, user, membership, tenant,
        remember=False, ip=ip, user_agent=user_agent, response=response,
    )
    await log_event(db, AuditEvent.LOGIN_SUCCESS, user_id=user.id, ip=ip, user_agent=user_agent)
    return resp


async def refresh_tokens(
    db: AsyncSession,
    raw_refresh: str,
    response: Response,
) -> AuthResponse:
    token_hash = hash_token(raw_refresh)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise ECLException("REFRESH_EXPIRED", "Refresh token invalid or expired.", 401)

    if rt.is_revoked:
        _log.warning("token_reuse_detected", family_id=rt.token_family_id)
        await _revoke_family(db, rt.token_family_id)
        raise ECLException(
            "TOKEN_REUSE",
            "Refresh token reuse detected. Please sign in again.",
            401,
        )

    if rt.expires_at < datetime.now(UTC):
        raise ECLException("REFRESH_EXPIRED", "Refresh token has expired.", 401)

    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise InvalidCredentialsError()

    membership_row = await _get_membership(db, user.id)
    if not membership_row:
        raise ECLException("NOT_TENANT_MEMBER", "No active workspace.", 403)
    membership, tenant = membership_row

    rt.is_revoked = True
    rt.last_used_at = datetime.now(UTC)

    settings = get_settings()
    new_raw = generate_raw_token()
    new_expires = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    new_rt = RefreshToken(
        id=new_ulid(),
        user_id=user.id,
        token_family_id=rt.token_family_id,
        token_hash=hash_token(new_raw),
        expires_at=new_expires,
    )
    db.add(new_rt)

    sess_result = await db.execute(
        select(Session).where(Session.refresh_token_id == rt.id)
    )
    sess = sess_result.scalar_one_or_none()
    if sess:
        idle_limit = timedelta(minutes=settings.session_idle_timeout_minutes)
        if datetime.now(UTC) - sess.last_active_at.replace(tzinfo=UTC) > idle_limit:
            raise ECLException(
                "IDLE_SESSION_EXPIRED",
                "Session expired due to inactivity. Please sign in again.",
                401,
            )
        sess.refresh_token_id = new_rt.id
        sess.last_active_at = datetime.now(UTC)

    access = create_access_token(
        {
            "sub": user.id,
            "email": user.email,
            "name": user.name,
            "role": membership.role,
            "tenant_id": tenant.id,
            "is_platform_admin": user.is_platform_admin,
        }
    )
    _set_refresh_cookie(response, new_raw, new_expires)

    return AuthResponse(
        data=TokenData(
            access_token=access,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=_user_out(user, membership, tenant),
        ),
        message="Token refreshed",
    )


async def _revoke_family(db: AsyncSession, family_id: str) -> None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_family_id == family_id)
    )
    for rt in result.scalars().all():
        rt.is_revoked = True


async def logout_user(
    db: AsyncSession,
    redis: Redis,
    access_token: str,
    raw_refresh: str | None,
    response: Response,
) -> None:
    from app.core.cache import blacklist_token
    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event

    user_id: str | None = None
    try:
        payload = decode_access_token(access_token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        user_id = str(payload.get("sub", "")) or None
        if jti and exp and user_id:
            expires_at = datetime.fromtimestamp(int(exp), UTC)
            await blacklist_token(redis, db, jti, user_id, expires_at, "logout")
    except ECLException:
        pass

    if raw_refresh:
        from sqlalchemy import delete

        token_hash = hash_token(raw_refresh)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()
        if rt:
            rt.is_revoked = True
            await db.execute(delete(Session).where(Session.refresh_token_id == rt.id))

    _clear_refresh_cookie(response)
    await log_event(db, AuditEvent.LOGOUT, user_id=user_id)


async def logout_all_user(
    db: AsyncSession,
    redis: Redis,
    user_id: str,
    access_token: str,
    response: Response,
) -> None:
    await logout_user(db, redis, access_token, None, response)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked.is_(False),
        )
    )
    for rt in result.scalars().all():
        rt.is_revoked = True
    from sqlalchemy import delete

    await db.execute(delete(Session).where(Session.user_id == user_id))
    _clear_refresh_cookie(response)


async def forgot_password(db: AsyncSession, request: ForgotPasswordRequest, ip: str = "") -> None:
    user = await _get_active_user_by_email(db, request.email)
    if user and user.is_active:
        await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
        )
        from sqlalchemy import update

        await db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )
        raw = generate_raw_token()
        db.add(
            PasswordResetToken(
                id=new_ulid(),
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )

        from app.core.email_dispatch import queue_email_in_outbox
        from app.modules.audit.models import AuditEvent
        from app.modules.audit.service import log_event

        await log_event(db, AuditEvent.PASSWORD_RESET_REQ, user_id=user.id, ip=ip)
        queue_email_in_outbox(
            db,
            task_name="send_reset_password_email",
            payload={"user_id": user.id, "raw_token": raw, "ip_address": ip},
        )


async def reset_password(db: AsyncSession, request: ResetPasswordRequest, ip: str = "") -> None:
    token_hash = hash_token(request.token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    prt = result.scalar_one_or_none()
    if not prt or prt.used_at or prt.expires_at < datetime.now(UTC):
        raise ECLException(
            "INVALID_RESET_TOKEN",
            "This reset link is invalid or has expired.",
            400,
        )

    user_result = await db.execute(select(User).where(User.id == prt.user_id))
    user = user_result.scalar_one()
    violations = await validate_password_full(request.password, name=user.name)
    if violations:
        code = violations[0]
        raise ECLException(code, _violation_detail(code), 422, field="password")

    user.hashed_password = hash_password(request.password)
    prt.used_at = datetime.now(UTC)

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )
    for rt in result.scalars().all():
        rt.is_revoked = True
    from sqlalchemy import delete

    await db.execute(delete(Session).where(Session.user_id == user.id))

    from app.core.email_dispatch import queue_email_in_outbox
    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event

    await log_event(db, AuditEvent.PASSWORD_RESET_DONE, user_id=user.id, ip=ip)
    queue_email_in_outbox(
        db,
        task_name="send_password_changed_email",
        payload={"user_id": user.id, "ip_address": ip},
    )


async def verify_email(db: AsyncSession, raw_token: str) -> None:
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
    )
    evt = result.scalar_one_or_none()
    if not evt or evt.verified_at or evt.expires_at < datetime.now(UTC):
        raise ECLException(
            "INVALID_VERIFY_TOKEN",
            "Verification link is invalid or expired.",
            400,
        )
    user_result = await db.execute(select(User).where(User.id == evt.user_id))
    user = user_result.scalar_one()
    user.is_email_verified = True
    evt.verified_at = datetime.now(UTC)

    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event

    await log_event(db, AuditEvent.EMAIL_VERIFIED, user_id=user.id)


async def resend_verification_email(
    db: AsyncSession,
    request: ResendVerificationRequest,
) -> None:
    result = await db.execute(
        select(User).where(
            User.email == request.email,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            User.is_email_verified.is_(False),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        return  # silent — do not reveal whether email exists

    # Invalidate any existing unused verification tokens for this user
    existing = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.verified_at.is_(None),
        )
    )
    for old_token in existing.scalars().all():
        old_token.expires_at = datetime.now(UTC)

    raw_verify = generate_raw_token(32)
    db.add(
        EmailVerificationToken(
            id=new_ulid(),
            user_id=user.id,
            token_hash=hash_token(raw_verify),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )

    from app.core.email_dispatch import queue_email_in_outbox

    queue_email_in_outbox(
        db,
        task_name="send_verification_email",
        payload={"user_id": user.id, "raw_token": raw_verify},
    )


async def switch_tenant(
    db: AsyncSession,
    user: User,
    request: SwitchTenantRequest,
) -> SwitchTenantData:
    row = await _get_membership(db, user.id, request.tenant_id)
    if not row:
        raise ECLException(
            "NOT_TENANT_MEMBER",
            "You are not a member of this workspace.",
            403,
        )
    membership, tenant = row
    settings = get_settings()
    access = create_access_token(
        {
            "sub": user.id,
            "email": user.email,
            "name": user.name,
            "role": membership.role,
            "tenant_id": tenant.id,
            "is_platform_admin": user.is_platform_admin,
        }
    )
    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import log_event

    await log_event(db, AuditEvent.TENANT_SWITCHED, user_id=user.id,
                    details={"tenant_id": tenant.id})
    return SwitchTenantData(
        access_token=access,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        role=membership.role,
        currency=tenant.currency or "USD",
        is_onboarding_complete=tenant.onboarding_completed_at is not None,
    )


def _violation_detail(code: str) -> str:
    details = {
        "PASSWORD_TOO_SHORT": "Password must be at least 8 characters.",
        "PASSWORD_MISSING_MIX": "Password must contain letters and numbers.",
        "PASSWORD_CONTAINS_FORBIDDEN": "Password contains a forbidden word.",
        "PASSWORD_PWNED": "This password has appeared in a known data breach.",
    }
    return details.get(code, "Password does not meet requirements.")
