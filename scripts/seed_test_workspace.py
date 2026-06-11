#!/usr/bin/env python3
"""Seed Segments and Collateral Types on the Zenith Bank dev tenant.

Idempotent. Safe to re-run. Requires `seed_dev_data.py` to have run first
(which creates the `Zenith Bank` tenant and its administrator).

The names seeded here must match (case-sensitive) the SEGMENT values and
collateral column headers in the dummy test data produced by
`generate_test_data.py`.
"""

import asyncio
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.enums import UserRole
from app.core.security import new_ulid
from app.database import AsyncSessionLocal
from app.modules.collateral.models import CollateralType
from app.modules.segments.models import Segment
from app.modules.tenants.models import Tenant, TenantMembership


TENANT_SLUG = "zenith-bank"

SEGMENTS = [
    ("Retail", "RET"),
    ("SME", "SME"),
    ("Corporate", "CORP"),
]

# (name, haircut_percent, time_to_realize_months)
COLLATERAL_TYPES = [
    ("Real Estate", Decimal("20.00"), 18),
    ("Motor Vehicle", Decimal("35.00"), 6),
    ("Cash Deposit", Decimal("0.00"), 1),
    ("Corporate Guarantee", Decimal("15.00"), 12),
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        ).scalar_one_or_none()
        if tenant is None:
            print(
                f"Tenant slug='{TENANT_SLUG}' not found. Run seed_dev_data.py first.",
                file=sys.stderr,
            )
            sys.exit(1)

        admin = (
            await db.execute(
                select(TenantMembership)
                .where(TenantMembership.tenant_id == tenant.id)
                .where(TenantMembership.role == UserRole.ADMINISTRATOR.value)
                .limit(1)
            )
        ).scalar_one_or_none()
        if admin is None:
            print(
                f"No administrator membership on tenant '{tenant.name}'. "
                "Re-run seed_dev_data.py.",
                file=sys.stderr,
            )
            sys.exit(1)
        creator_id = admin.user_id

        created_segments = 0
        for name, code in SEGMENTS:
            existing = (
                await db.execute(
                    select(Segment)
                    .where(Segment.tenant_id == tenant.id)
                    .where(Segment.name == name)
                    .where(Segment.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if existing:
                continue
            db.add(
                Segment(
                    id=new_ulid(),
                    tenant_id=tenant.id,
                    name=name,
                    code=code,
                    is_active=True,
                    created_by_user_id=creator_id,
                )
            )
            created_segments += 1

        created_collateral = 0
        for name, haircut, ttr in COLLATERAL_TYPES:
            existing = (
                await db.execute(
                    select(CollateralType)
                    .where(CollateralType.tenant_id == tenant.id)
                    .where(CollateralType.name == name)
                    .where(CollateralType.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if existing:
                continue
            db.add(
                CollateralType(
                    id=new_ulid(),
                    tenant_id=tenant.id,
                    name=name,
                    haircut=haircut,
                    time_to_realize=ttr,
                    created_by_user_id=creator_id,
                )
            )
            created_collateral += 1

        await db.commit()
        print(
            f"Tenant '{tenant.name}': +{created_segments} segments, "
            f"+{created_collateral} collateral types "
            f"(already-present rows untouched)."
        )


if __name__ == "__main__":
    asyncio.run(main())
