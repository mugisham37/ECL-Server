from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ECLException
from app.core.security import new_ulid
from app.modules.collateral.models import CollateralType
from app.modules.collateral.schemas import (
    BatchCreateCollateralTypesRequest,
    CollateralTypeOut,
    CreateCollateralTypeRequest,
    UpdateCollateralTypeRequest,
)


def _to_out(c: CollateralType) -> CollateralTypeOut:
    return CollateralTypeOut(
        id=c.id,
        name=c.name,
        haircut=c.haircut,
        time_to_realize=c.time_to_realize,
        created_at=c.created_at,
    )


async def _check_name_unique(
    db: AsyncSession, tenant_id: str, name: str, exclude_id: str | None = None
) -> None:
    q = select(CollateralType).where(
        CollateralType.tenant_id == tenant_id,
        CollateralType.name == name.strip(),
        CollateralType.deleted_at.is_(None),
    )
    if exclude_id:
        q = q.where(CollateralType.id != exclude_id)
    result = await db.execute(q)
    if result.scalar_one_or_none():
        raise ECLException(
            "COLLATERAL_NAME_TAKEN",
            f"A collateral type named '{name}' already exists in this workspace.",
            409,
            field="name",
        )


async def list_collateral_types(db: AsyncSession, tenant_id: str) -> list[CollateralTypeOut]:
    result = await db.execute(
        select(CollateralType)
        .where(CollateralType.tenant_id == tenant_id, CollateralType.deleted_at.is_(None))
        .order_by(CollateralType.name)
    )
    return [_to_out(c) for c in result.scalars().all()]


async def create_collateral_type(
    db: AsyncSession, tenant_id: str, user_id: str, req: CreateCollateralTypeRequest
) -> CollateralTypeOut:
    await _check_name_unique(db, tenant_id, req.name)
    c = CollateralType(
        id=new_ulid(),
        tenant_id=tenant_id,
        name=req.name.strip(),
        haircut=req.haircut,
        time_to_realize=req.time_to_realize,
        created_by_user_id=user_id,
    )
    db.add(c)
    await db.flush()
    return _to_out(c)


async def batch_create_collateral_types(
    db: AsyncSession, tenant_id: str, user_id: str, req: BatchCreateCollateralTypesRequest
) -> list[CollateralTypeOut]:
    names = [item.name.strip() for item in req.items]
    if len(names) != len(set(n.lower() for n in names)):
        raise ECLException("DUPLICATE_NAMES", "Duplicate collateral type names in batch.", 400)

    existing = await db.execute(
        select(CollateralType.name).where(
            CollateralType.tenant_id == tenant_id,
            CollateralType.name.in_(names),
            CollateralType.deleted_at.is_(None),
        )
    )
    taken = {r[0] for r in existing.all()}
    if taken:
        raise ECLException(
            "COLLATERAL_NAME_TAKEN",
            f"Collateral types already exist: {', '.join(sorted(taken))}",
            409,
        )

    created = []
    for item in req.items:
        c = CollateralType(
            id=new_ulid(),
            tenant_id=tenant_id,
            name=item.name.strip(),
            haircut=item.haircut,
            time_to_realize=item.time_to_realize,
            created_by_user_id=user_id,
        )
        db.add(c)
        created.append(c)

    await db.flush()
    return [_to_out(c) for c in created]


async def update_collateral_type(
    db: AsyncSession, tenant_id: str, collateral_id: str, req: UpdateCollateralTypeRequest
) -> CollateralTypeOut:
    result = await db.execute(
        select(CollateralType).where(
            CollateralType.id == collateral_id,
            CollateralType.tenant_id == tenant_id,
            CollateralType.deleted_at.is_(None),
        )
    )
    c = result.scalar_one_or_none()
    if not c:
        raise ECLException("RESOURCE_NOT_FOUND", "Collateral type not found.", 404)

    if req.name is not None:
        await _check_name_unique(db, tenant_id, req.name, exclude_id=collateral_id)
        c.name = req.name.strip()
    if req.haircut is not None:
        c.haircut = req.haircut
    if req.time_to_realize is not None:
        c.time_to_realize = req.time_to_realize
    return _to_out(c)


async def delete_collateral_type(
    db: AsyncSession, tenant_id: str, collateral_id: str
) -> None:
    result = await db.execute(
        select(CollateralType).where(
            CollateralType.id == collateral_id,
            CollateralType.tenant_id == tenant_id,
            CollateralType.deleted_at.is_(None),
        )
    )
    c = result.scalar_one_or_none()
    if not c:
        raise ECLException("RESOURCE_NOT_FOUND", "Collateral type not found.", 404)
    c.deleted_at = datetime.now(UTC)
