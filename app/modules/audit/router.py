import csv
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DbSession, PlatformAdmin
from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditLogOut, AuditLogsResponse

router = APIRouter(prefix="/platform", tags=["audit"])


def _apply_audit_filters(
    q,
    *,
    user_id: str | None,
    event_type: str | None,
    start: datetime | None,
    end: datetime | None,
):
    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    if event_type:
        q = q.where(AuditLog.event_type == event_type)
    if start:
        q = q.where(AuditLog.created_at >= start)
    if end:
        q = q.where(AuditLog.created_at <= end)
    return q


async def audit_log_csv_generator(
    db: AsyncSession,
    *,
    user_id: str | None,
    event_type: str | None,
    start: datetime | None,
    end: datetime | None,
):
    header = io.StringIO()
    writer = csv.writer(header)
    writer.writerow(
        ["timestamp", "event_type", "status", "user_id", "ip_address_hash", "tenant_id", "details"]
    )
    yield header.getvalue()

    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(50000)
    query = _apply_audit_filters(
        query, user_id=user_id, event_type=event_type, start=start, end=end
    )

    result = await db.stream_scalars(query)
    row_count = 0
    async for row in result:
        row_count += 1
        row_io = io.StringIO()
        row_writer = csv.writer(row_io)
        row_writer.writerow(
            [
                row.created_at.isoformat() if row.created_at else "",
                row.event_type or "",
                row.status or "",
                row.user_id or "",
                row.ip_address_hash or "",
                row.tenant_id or "",
                str(row.details) if row.details else "",
            ]
        )
        yield row_io.getvalue()

    if row_count >= 50000:
        yield "# Export capped at 50,000 rows. Use date filters to narrow the range.\n"


@router.get("/audit-logs")
async def list_audit_logs(
    db: DbSession,
    _admin=Depends(PlatformAdmin),
    user_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    export: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
):
    if export == "csv":
        filename = f"audit-log-{date.today().isoformat()}.csv"
        return StreamingResponse(
            audit_log_csv_generator(
                db,
                user_id=user_id,
                event_type=event_type,
                start=start,
                end=end,
            ),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    q = select(AuditLog)
    q = _apply_audit_filters(
        q, user_id=user_id, event_type=event_type, start=start, end=end
    )
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
