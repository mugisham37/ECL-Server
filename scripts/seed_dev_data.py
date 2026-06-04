#!/usr/bin/env python3
"""Seed development tenants and users."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.enums import MemberStatus, UserRole
from app.core.security import hash_password, new_ulid
from app.database import AsyncSessionLocal
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant, TenantMembership


async def main() -> None:
    async with AsyncSessionLocal() as db:
        if (await db.execute(select(Tenant).limit(1))).scalar_one_or_none():
            print("Dev data already seeded.")
            return
        for company, email, name in [
            ("Zenith Bank", "jane@zenith.com", "Jane Smith"),
            ("Acme Corp", "bob@acme.com", "Bob Jones"),
        ]:
            tenant = Tenant(id=new_ulid(), name=company, slug=company.lower().replace(" ", "-"))
            user = User(
                id=new_ulid(),
                email=email,
                name=name,
                hashed_password=hash_password("TestPass123!"),
                is_email_verified=True,
            )
            membership = TenantMembership(
                id=new_ulid(),
                user_id=user.id,
                tenant_id=tenant.id,
                role=UserRole.ADMINISTRATOR.value,
                status=MemberStatus.ACTIVE.value,
            )
            db.add_all([tenant, user, membership])
        await db.commit()
        print("Seeded 2 tenants with admin users (password: TestPass123!).")


if __name__ == "__main__":
    asyncio.run(main())
