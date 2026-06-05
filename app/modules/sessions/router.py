from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.core.security import decode_access_token
from app.dependencies import CurrentUser, DbSession, RedisClient
from app.modules.auth.schemas import MessageResponse
from app.modules.sessions.schemas import (
    AvatarUploadResponse,
    ChangePasswordRequest,
    MeResponse,
    SessionsResponse,
    TOTPBackupCodesResponse,
    TOTPConfirmRequest,
    TOTPDisableRequest,
    TOTPEnrollResponse,
    UpdateProfileRequest,
)
from app.modules.sessions import service

router = APIRouter(tags=["me"])
_bearer = HTTPBearer()


def _get_refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(get_settings().refresh_cookie_name)


@router.get("/me")
async def get_me_endpoint(
    db: DbSession,
    user: CurrentUser,
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> MeResponse:
    payload = decode_access_token(creds.credentials)
    data = await service.get_me(db, user, payload.get("tenant_id"))
    return MeResponse(data=data)


@router.patch("/me", status_code=status.HTTP_204_NO_CONTENT)
async def patch_me(body: UpdateProfileRequest, db: DbSession, user: CurrentUser) -> None:
    await service.update_profile(db, user, body)


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def patch_password(
    body: ChangePasswordRequest,
    db: DbSession,
    user: CurrentUser,
) -> None:
    await service.change_password(db, user, body)


@router.post("/me/avatar")
async def upload_avatar_endpoint(
    file: UploadFile = File(...),
    db: DbSession,
    user: CurrentUser,
) -> AvatarUploadResponse:
    content = await file.read()
    content_type = file.content_type or ""
    url = await service.upload_avatar(db, user, content, content_type)
    return AvatarUploadResponse(data={"avatar_url": url})


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar_endpoint(db: DbSession, user: CurrentUser) -> None:
    await service.delete_avatar(db, user)


@router.get("/me/sessions")
async def get_sessions(request: Request, db: DbSession, user: CurrentUser) -> SessionsResponse:
    raw_refresh = _get_refresh_cookie(request)
    current_rt_id = await service.resolve_current_rt_id(db, raw_refresh)
    sessions = await service.list_sessions(db, user.id, current_rt_id)
    return SessionsResponse(data=sessions)


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> None:
    raw_refresh = _get_refresh_cookie(request)
    current_rt_id = await service.resolve_current_rt_id(db, raw_refresh)
    current_session_id = await service.resolve_current_session_id(db, user.id, current_rt_id)
    await service.revoke_session(db, user.id, session_id, current_session_id)


@router.delete("/me/sessions")
async def delete_other_sessions(request: Request, db: DbSession, user: CurrentUser) -> MessageResponse:
    raw_refresh = _get_refresh_cookie(request)
    current_rt_id = await service.resolve_current_rt_id(db, raw_refresh)
    current_session_id = await service.resolve_current_session_id(db, user.id, current_rt_id)
    count = await service.revoke_other_sessions(db, user.id, current_session_id)
    return MessageResponse(message=f"{count} other sessions revoked.")


@router.post("/me/mfa/totp/enroll", status_code=status.HTTP_200_OK)
async def enroll_totp_start_endpoint(
    db: DbSession,
    redis: RedisClient,
    user: CurrentUser,
) -> TOTPEnrollResponse:
    return await service.enroll_totp_start(db, redis, user)


@router.post("/me/mfa/totp/confirm", status_code=status.HTTP_200_OK)
async def enroll_totp_confirm_endpoint(
    body: TOTPConfirmRequest,
    db: DbSession,
    redis: RedisClient,
    user: CurrentUser,
) -> TOTPBackupCodesResponse:
    return await service.enroll_totp_confirm(db, redis, user, body)


@router.delete("/me/mfa/totp", status_code=status.HTTP_204_NO_CONTENT)
async def disable_totp_endpoint(
    body: TOTPDisableRequest,
    db: DbSession,
    user: CurrentUser,
) -> None:
    await service.disable_totp(db, user, body)
