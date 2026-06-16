#!/usr/bin/env python3
"""Truncate all application data — keeps tables and alembic_version."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import engine


async def truncate_all() -> list[str]:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename != 'alembic_version'
                ORDER BY tablename
                """
            )
        )
        tables = [row[0] for row in result.fetchall()]
        if not tables:
            return tables

        quoted = ", ".join(f'"{name}"' for name in tables)
        await conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
        return tables


async def main() -> None:
    parser = argparse.ArgumentParser(description="Truncate all ECL application data.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    args = parser.parse_args()

    if not args.yes:
        print("This will DELETE all rows from every table (schema is kept).")
        print("Type 'yes' to continue:", end=" ")
        if input().strip().lower() != "yes":
            print("Aborted.")
            return

    tables = await truncate_all()
    if not tables:
        print("No application tables found.")
        return

    print(f"Truncated {len(tables)} tables:")
    for name in tables:
        print(f"  - {name}")


if __name__ == "__main__":
    asyncio.run(main())
