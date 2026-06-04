from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ECLException
from app.core.security import new_ulid
from app.modules.segments.models import Segment
from app.modules.segments.schemas import (
    BatchCreateSegmentsRequest,
    CreateSegmentRequest,
    SegmentOut,
    UpdateSegmentRequest,
)


def _to_out(s: Segment) -> SegmentOut:
    return SegmentOut(id=s.id, name=s.name, code=s.code, created_at=s.created_at)


async def _check_name_unique(
    db: AsyncSession, tenant_id: str, name: str, exclude_id: str | None = None
) -> None:
    q = select(Segment).where(
        Segment.tenant_id == tenant_id,
        Segment.name == name.strip(),
        Segment.deleted_at.is_(None),
    )
    if exclude_id:
        from sqlalchemy import and_

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
    result = await db.execute(
        select(Segment)
        .where(Segment.tenant_id == tenant_id, Segment.deleted_at.is_(None))
        .order_by(Segment.name)
    )
    return [_to_out(s) for s in result.scalars().all()]


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
    db: AsyncSession, tenant_id: str, segment_id: str, req: UpdateSegmentRequest
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
