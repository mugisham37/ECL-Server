from fastapi import APIRouter, Depends, Request, Response, status

from app.core.limiter import limiter
from app.dependencies import CurrentUser, DbSession, get_client_ip
from app.modules.auth.schemas import AuthResponse
from app.modules.invites.schemas import (
    AcceptInviteRequest,
    BatchInviteRequest,
    BatchInviteResponse,
    InviteValidateResponse,
    SendInviteRequest,
)
from app.modules.invites import service

router = APIRouter(prefix="/invites", tags=["invites"])


@router.get("/validate/{token}")
async def validate_invite_endpoint(token: str, db: DbSession) -> InviteValidateResponse:
    data = await service.validate_invite(db, token)
    return InviteValidateResponse(data=data)


@router.post("/accept", status_code=status.HTTP_201_CREATED)
async def accept_invite_endpoint(
    request: Request,
    body: AcceptInviteRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    return await service.accept_invite(
        db,
        body,
        get_client_ip(request.headers.get("x-forwarded-for")),
        request.headers.get("user-agent"),
        response,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def send_invite_endpoint(
    body: SendInviteRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict[str, str]:
    from app.dependencies import require_tenant_admin

    await require_tenant_admin(body.tenant_id, user, db)
    inv = await service.send_invite(db, body, user)
    return {"data": {"id": inv.id}, "message": "Invitation sent."}


@router.post("/batch", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def batch_invite_endpoint(
    request: Request,
    body: BatchInviteRequest,
    db: DbSession,
    user: CurrentUser,
) -> BatchInviteResponse:
    from app.dependencies import require_tenant_admin

    await require_tenant_admin(body.tenant_id, user, db)
    results = await service.batch_send_invites(db, body, user)
    return BatchInviteResponse(data=results, message=f"{len(results)} invitation(s) sent.")


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invite(
    invite_id: str,
    db: DbSession,
    user: CurrentUser,
) -> None:
    from sqlalchemy import select
    from app.core.enums import InvitationStatus
    from app.modules.invites.models import Invitation
    from app.dependencies import require_tenant_admin
    from app.core.exceptions import ECLException

    result = await db.execute(select(Invitation).where(Invitation.id == invite_id))
    inv = result.scalar_one_or_none()
    if not inv:
        raise ECLException("RESOURCE_NOT_FOUND", "Invitation not found.", 404)
    await require_tenant_admin(inv.tenant_id, user, db)
    inv.status = InvitationStatus.CANCELLED.value


@router.post("/{invite_id}/resend")
async def resend_invite(
    invite_id: str,
    db: DbSession,
    user: CurrentUser,
) -> dict[str, str]:
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select
    from app.core.security import generate_raw_token, hash_token
    from app.modules.invites.models import Invitation
    from app.dependencies import require_tenant_admin
    from app.core.exceptions import ECLException

    result = await db.execute(select(Invitation).where(Invitation.id == invite_id))
    inv = result.scalar_one_or_none()
    if not inv:
        raise ECLException("RESOURCE_NOT_FOUND", "Invitation not found.", 404)
    await require_tenant_admin(inv.tenant_id, user, db)
    raw = generate_raw_token()
    inv.token_hash = hash_token(raw)
    inv.expires_at = datetime.now(UTC) + timedelta(days=7)
    return {"message": "Invitation resent."}
