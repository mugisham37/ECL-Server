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
    RegisterRequest,
    ResetPasswordRequest,
    SwitchTenantData,
    SwitchTenantRequest,
    TokenData,
    UserOut,
)
from app.modules.auth.utils import hash_ip, parse_device, unique_slug, user_initials
from app.modules.sessions.models import RefreshToken, Session
from app.modules.tenants.models import Tenant, TenantMembership


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
        is_email_verified=user.is_email_verified,
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
        is_email_verified=False,
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
    return auth_resp


async def login_user(
    db: AsyncSession,
    request: LoginRequest,
    ip: str,
    user_agent: str | None,
    response: Response,
) -> AuthResponse:
    user = await _get_active_user_by_email(db, request.email)
    valid = verify_password_or_dummy(
        request.password, user.hashed_password if user else None
    )
    if not user or not valid:
        if user:
            await check_lockout(user)
            await handle_failed_login(db, user)
        raise InvalidCredentialsError()

    await check_lockout(user)
    if not user.is_active:
        raise AccountDisabledError()

    if not valid:
        await handle_failed_login(db, user)
        raise InvalidCredentialsError()

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)

    membership_row = await _get_membership(db, user.id)
    if not membership_row:
        raise ECLException("NOT_TENANT_MEMBER", "No active workspace membership.", 403)
    membership, tenant = membership_row

    return await _create_session_tokens(
        db,
        user,
        membership,
        tenant,
        remember=request.remember,
        ip=ip,
        user_agent=user_agent,
        response=response,
    )


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
        sess.refresh_token_id = new_rt.id
        sess.last_active_at = datetime.now(UTC)

    access = create_access_token(
        {
            "sub": user.id,
            "email": user.email,
            "name": user.name,
            "role": membership.role,
            "tenant_id": tenant.id,
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
    settings = get_settings()
    try:
        payload = decode_access_token(access_token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            ttl = int(exp) - int(datetime.now(UTC).timestamp())
            await redis.setex(f"blacklist:jti:{jti}", max(ttl, 1), "1")
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


async def forgot_password(db: AsyncSession, request: ForgotPasswordRequest) -> None:
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


async def reset_password(db: AsyncSession, request: ResetPasswordRequest) -> None:
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
        }
    )
    return SwitchTenantData(
        access_token=access,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        role=membership.role,
    )


def _violation_detail(code: str) -> str:
    details = {
        "PASSWORD_TOO_SHORT": "Password must be at least 8 characters.",
        "PASSWORD_MISSING_MIX": "Password must contain letters and numbers.",
        "PASSWORD_CONTAINS_FORBIDDEN": "Password contains a forbidden word.",
        "PASSWORD_PWNED": "This password has appeared in a known data breach.",
    }
    return details.get(code, "Password does not meet requirements.")
