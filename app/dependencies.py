from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.cache import get_redis_client, is_token_blacklisted
from app.core.enums import MemberStatus, UserRole
from app.core.exceptions import ECLException
from app.core.security import decode_access_token
from app.database import get_db
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, TenantMembership

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis_client)]


async def get_current_user(
    db: DbSession,
    redis: RedisClient,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if not creds or not creds.credentials:
        raise ECLException("TOKEN_INVALID", "Authentication required.", 401)
    payload = decode_access_token(creds.credentials)
    jti = payload.get("jti")
    if jti and await is_token_blacklisted(redis, jti, db):
        raise ECLException("TOKEN_BLACKLISTED", "Token has been revoked.", 401)
    user_id = payload.get("sub")
    if not user_id:
        raise ECLException("TOKEN_INVALID", "Invalid token payload.", 401)
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise ECLException("ACCOUNT_DISABLED", "Account is disabled.", 403)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_tenant_member(
    tenant_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> TenantMembership:
    result = await db.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == current_user.id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == MemberStatus.ACTIVE.value,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise ECLException("NOT_TENANT_MEMBER", "Not a member of this workspace.", 403)
    return m


async def require_tenant_admin(
    tenant_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> TenantMembership:
    m = await require_tenant_member(tenant_id, current_user, db)
    if m.role != UserRole.ADMINISTRATOR.value:
        raise ECLException("INSUFFICIENT_ROLE", "Administrator role required.", 403)
    return m


async def require_tenant_analyst_or_admin(
    tenant_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> TenantMembership:
    m = await require_tenant_member(tenant_id, current_user, db)
    if m.role not in (UserRole.ADMINISTRATOR.value, UserRole.ANALYST.value):
        raise ECLException(
            "INSUFFICIENT_ROLE",
            "Analyst or administrator role required.",
            403,
        )
    return m


async def require_platform_admin(current_user: CurrentUser) -> User:
    if not current_user.is_platform_admin:
        raise ECLException(
            "PLATFORM_ADMIN_REQUIRED",
            "Platform administrator privileges required.",
            403,
        )
    return current_user


PlatformAdmin = Annotated[User, Depends(require_platform_admin)]


def get_client_ip(x_forwarded_for: str | None = None) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers and x_forwarded_for:
        ips = [ip.strip() for ip in x_forwarded_for.split(",") if ip.strip()]
        idx = max(0, len(ips) - settings.trusted_proxy_count)
        return ips[idx] if ips else "127.0.0.1"
    return "127.0.0.1"


def get_user_agent(
    user_agent: Annotated[str | None, Header(alias="User-Agent")] = None,
) -> str | None:
    return user_agent
