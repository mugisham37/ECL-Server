import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, strong_password: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Zenith Bank",
            "email": "newuser@zenith.com",
            "name": "Jane Smith",
            "password": strong_password,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body["data"]
    assert body["data"]["user"]["role"] == "administrator"
    assert body["data"]["user"]["tenant_name"] == "Zenith Bank"
    assert body["data"]["user"]["is_email_verified"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, strong_password: str) -> None:
    payload = {
        "company_name": "Corp A",
        "email": "dup@test.com",
        "name": "User One",
        "password": strong_password,
    }
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json={**payload, "company_name": "Corp B"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "EMAIL_TAKEN"


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Test Co",
            "email": "weak@test.com",
            "name": "Test User",
            "password": "short",
        },
    )
    assert resp.status_code == 422
