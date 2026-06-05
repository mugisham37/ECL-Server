from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ECLException
from app.core.security import new_ulid
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import log_event
from app.modules.results.models import EadResult
from app.modules.runs.models import Run
from app.modules.segments.models import Segment
from app.modules.segments.schemas import (
    BatchCreateSegmentsRequest,
    CreateSegmentRequest,
    SegmentOut,
    UpdateSegmentRequest,
)


def _runs_count_subquery(tenant_id: str, segment_name):
    return (
        select(func.count(func.distinct(Run.id)))
        .select_from(Run)
        .join(EadResult, Run.id == EadResult.run_id)
        .where(
            Run.tenant_id == tenant_id,
            EadResult.segment == segment_name,
            Run.status == "complete",
        )
        .correlate(Segment)
        .scalar_subquery()
    )


def _to_out(s: Segment, runs_count: int = 0) -> SegmentOut:
    return SegmentOut(
        id=s.id,
        name=s.name,
        code=s.code,
        is_active=s.is_active,
        runs_count=runs_count,
        created_at=s.created_at,
    )


async def _check_name_unique(
    db: AsyncSession, tenant_id: str, name: str, exclude_id: str | None = None
) -> None:
    q = select(Segment).where(
        Segment.tenant_id == tenant_id,
        Segment.name == name.strip(),
        Segment.deleted_at.is_(None),
    )
    if exclude_id:
        q = q.where(Segment.id != exclude_id)
    result = await db.execute(q)
    if result.scalar_one_or_none():
        raise ECLException(
            "SEGMENT_NAME_TAKEN",
            f"A segment named '{name}' already exists in this workspace.",
            409,
            field="name",
        )


async def list_segments(db: AsyncSession, tenant_id: str) -> list[SegmentOut]:
    runs_subq = _runs_count_subquery(tenant_id, Segment.name)
    result = await db.execute(
        select(Segment, runs_subq.label("runs_count"))
        .where(Segment.tenant_id == tenant_id, Segment.deleted_at.is_(None))
        .order_by(Segment.name)
    )
    return [_to_out(s, runs_count or 0) for s, runs_count in result.all()]


async def create_segment(
    db: AsyncSession, tenant_id: str, user_id: str, req: CreateSegmentRequest
) -> SegmentOut:
    await _check_name_unique(db, tenant_id, req.name)
    s = Segment(
        id=new_ulid(),
        tenant_id=tenant_id,
        name=req.name.strip(),
        code=req.code.strip() if req.code else None,
        created_by_user_id=user_id,
    )
    db.add(s)
    await db.flush()
    return _to_out(s)


async def batch_create_segments(
    db: AsyncSession, tenant_id: str, user_id: str, req: BatchCreateSegmentsRequest
) -> list[SegmentOut]:
    names = [item.name.strip() for item in req.segments]
    if len(names) != len(set(n.lower() for n in names)):
        raise ECLException("DUPLICATE_NAMES", "Duplicate segment names in batch.", 400)

    existing = await db.execute(
        select(Segment.name).where(
            Segment.tenant_id == tenant_id,
            Segment.name.in_(names),
            Segment.deleted_at.is_(None),
        )
    )
    taken = {r[0] for r in existing.all()}
    if taken:
        raise ECLException(
            "SEGMENT_NAME_TAKEN",
            f"Segments already exist: {', '.join(sorted(taken))}",
            409,
        )

    created = []
    for item in req.segments:
        s = Segment(
            id=new_ulid(),
            tenant_id=tenant_id,
            name=item.name.strip(),
            code=item.code.strip() if item.code else None,
            created_by_user_id=user_id,
        )
        db.add(s)
        created.append(s)

    await db.flush()
    return [_to_out(s) for s in created]


async def update_segment(
    db: AsyncSession,
    tenant_id: str,
    segment_id: str,
    req: UpdateSegmentRequest,
    user_id: str | None = None,
) -> SegmentOut:
    result = await db.execute(
        select(Segment).where(
            Segment.id == segment_id,
            Segment.tenant_id == tenant_id,
            Segment.deleted_at.is_(None),
        )
    )
    s = result.scalar_one_or_none()
    if not s:
        raise ECLException("RESOURCE_NOT_FOUND", "Segment not found.", 404)

    if req.name is not None:
        await _check_name_unique(db, tenant_id, req.name, exclude_id=segment_id)
        s.name = req.name.strip()
    if req.code is not None:
        s.code = req.code.strip() or None
    if req.is_active is not None:
        s.is_active = req.is_active
        if user_id:
            await log_event(
                db,
                AuditEvent.SEGMENT_UPDATED,
                user_id=user_id,
                tenant_id=tenant_id,
                details={"segment_id": segment.id, "is_active": req.is_active},
            )
    return _to_out(s)


async def delete_segment(db: AsyncSession, tenant_id: str, segment_id: str) -> None:
    result = await db.execute(
        select(Segment).where(
            Segment.id == segment_id,
            Segment.tenant_id == tenant_id,
            Segment.deleted_at.is_(None),
        )
    )
    s = result.scalar_one_or_none()
    if not s:
        raise ECLException("RESOURCE_NOT_FOUND", "Segment not found.", 404)
    s.deleted_at = datetime.now(UTC)
