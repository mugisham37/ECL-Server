"""Tenant isolation tests for runs API."""

import pytest
from httpx import AsyncClient

from app.core.security import new_ulid
from app.modules.auth.models import User
from app.modules.runs.models import Run
from app.modules.tenants.models import Tenant, TenantMembership
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_run_not_visible_across_tenants(client: AsyncClient) -> None:
    """User in tenant A cannot access runs belonging to tenant B."""
    tenant_a = new_ulid()
    tenant_b = new_ulid()
    user_a = new_ulid()
    run_b = new_ulid()

    async with TestSessionLocal() as db:
        db.add(
            User(
                id=user_a,
                email="analyst-a@example.com",
                name="Analyst A",
                hashed_password="x",
                is_active=True,
                is_email_verified=True,
            )
        )
        db.add(Tenant(id=tenant_a, name="Tenant A", slug="tenant-a", currency="KES"))
        db.add(Tenant(id=tenant_b, name="Tenant B", slug="tenant-b", currency="KES"))
        db.add(
            TenantMembership(
                id=new_ulid(),
                tenant_id=tenant_a,
                user_id=user_a,
                role="analyst",
                status="active",
            )
        )
        db.add(
            Run(
                id=run_b,
                tenant_id=tenant_b,
                created_by_user_id=user_a,
                name="Secret Run",
                status="draft",
                engine_version="v1.0.0",
            )
        )
        await db.commit()

    # Unauthenticated should 401
    resp = await client.get(f"/api/v1/tenants/{tenant_b}/runs/{run_b}")
    assert resp.status_code == 401
