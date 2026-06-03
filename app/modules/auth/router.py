from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.core.exceptions import ECLException
from app.core.limiter import limiter
from app.core.security import decode_access_token
from app.dependencies import CurrentUser, DbSession, RedisClient, get_client_ip
from app.modules.auth.schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SwitchTenantRequest,
    SwitchTenantResponse,
    ValidateTokenData,
    ValidateTokenResponse,
)
from app.modules.auth import service

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    return await service.register_user(
        db,
        body,
        get_client_ip(request.headers.get("x-forwarded-for")),
        request.headers.get("user-agent"),
        response,
    )


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    return await service.login_user(
        db,
        body,
        get_client_ip(request.headers.get("x-forwarded-for")),
        request.headers.get("user-agent"),
        response,
    )


@router.post("/refresh")
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    ecl_refresh: str | None = Cookie(None),
) -> AuthResponse:
    settings = get_settings()
    raw = ecl_refresh
    if not raw:
        raise ECLException("REFRESH_EXPIRED", "Refresh token required.", 401)
    return await service.refresh_tokens(db, raw, response)


@router.post("/logout")
async def logout(
    response: Response,
    db: DbSession,
    redis: RedisClient,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ecl_refresh: str | None = Cookie(None),
) -> MessageResponse:
    token = creds.credentials if creds else ""
    await service.logout_user(db, redis, token, ecl_refresh, response)
    return MessageResponse(message="Logged out successfully.")


@router.post("/logout-all")
async def logout_all(
    response: Response,
    db: DbSession,
    redis: RedisClient,
    user: CurrentUser,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> MessageResponse:
    token = creds.credentials if creds else ""
    await service.logout_all_user(db, redis, user.id, token, response)
    return MessageResponse(message="All sessions revoked.")


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password_endpoint(
    request: Request,
    body: ForgotPasswordRequest,
    db: DbSession,
) -> MessageResponse:
    await service.forgot_password(db, body)
    return MessageResponse(
        message="If that email is registered, a reset link has been sent."
    )


@router.post("/reset-password")
async def reset_password_endpoint(
    body: ResetPasswordRequest,
    db: DbSession,
) -> MessageResponse:
    await service.reset_password(db, body)
    return MessageResponse(message="Password updated successfully.")


@router.get("/verify-email/{token}")
async def verify_email_endpoint(token: str, db: DbSession) -> MessageResponse:
    await service.verify_email(db, token)
    return MessageResponse(message="Email verified successfully.")


@router.post("/switch-tenant")
async def switch_tenant_endpoint(
    body: SwitchTenantRequest,
    db: DbSession,
    user: CurrentUser,
) -> SwitchTenantResponse:
    data = await service.switch_tenant(db, user, body)
    return SwitchTenantResponse(data=data, message="Tenant switched.")


@router.post("/validate-token")
async def validate_token_endpoint(
    redis: RedisClient,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> ValidateTokenResponse:
    if not creds:
        raise ECLException("TOKEN_INVALID", "Authentication required.", 401)
    payload = decode_access_token(creds.credentials)
    from app.core.cache import is_token_blacklisted

    jti = payload.get("jti")
    if jti and await is_token_blacklisted(redis, jti):
        raise ECLException("TOKEN_BLACKLISTED", "Token revoked.", 401)
    return ValidateTokenResponse(
        data=ValidateTokenData(
            user_id=str(payload["sub"]),
            email=str(payload["email"]),
            role=str(payload["role"]),
            tenant_id=str(payload["tenant_id"]),
            exp=int(payload["exp"]),
        )
    )

