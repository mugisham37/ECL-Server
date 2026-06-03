#!/usr/bin/env python3
"""Seed platform superadmin."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.security import hash_password, new_ulid
from app.database import AsyncSessionLocal
from app.modules.auth.models import User


async def main() -> None:
    email = os.environ.get("SUPERADMIN_EMAIL", "admin@eclplatform.com")
    password = os.environ.get("SUPERADMIN_PASSWORD", "SuperAdmin123!")
    name = os.environ.get("SUPERADMIN_NAME", "Platform Admin")
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email.lower()))
        if existing.scalar_one_or_none():
            print(f"Superadmin {email} already exists.")
            return
        user = User(
            id=new_ulid(),
            email=email.lower(),
            name=name,
            hashed_password=hash_password(password),
            is_email_verified=True,
            is_platform_admin=True,
        )
        db.add(user)
        await db.commit()
        print(f"Created superadmin: {email}")


if __name__ == "__main__":
    asyncio.run(main())
