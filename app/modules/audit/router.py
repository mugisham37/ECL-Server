from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DbSession, PlatformAdmin
from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditLogOut, AuditLogsResponse
from app.modules.auth.models import User

router = APIRouter(prefix="/platform", tags=["audit"])


@router.get("/audit-logs")
async def list_audit_logs(
    db: DbSession,
    _admin: User = Depends(PlatformAdmin),
    user_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> AuditLogsResponse:
    q = select(AuditLog)
    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    if event_type:
        q = q.where(AuditLog.event_type == event_type)
    if start:
        q = q.where(AuditLog.created_at >= start)
    if end:
        q = q.where(AuditLog.created_at <= end)

    q = q.order_by(AuditLog.created_at.desc())
    q = q.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(q)
    entries = result.scalars().all()
    return AuditLogsResponse(
        data=[
            AuditLogOut(
                id=e.id,
                user_id=e.user_id,
                event_type=e.event_type,
                status=e.status,
                error_code=e.error_code,
                details=e.details,
                created_at=e.created_at,
            )
            for e in entries
        ]
    )
