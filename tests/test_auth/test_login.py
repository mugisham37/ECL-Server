import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, email: str, password: str) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "Login Test Co",
            "email": email,
            "name": "Login User",
            "password": password,
        },
    )


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, strong_password: str) -> None:
    email = "login_ok@test.com"
    await _register(client, email, strong_password)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": strong_password, "remember": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]
    assert "ecl_refresh" in resp.cookies or resp.cookies.get("ecl_refresh") is not None


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, strong_password: str) -> None:
    email = "login_bad@test.com"
    await _register(client, email, strong_password)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPass99!"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "AnyPass123!"},
    )
    assert resp.status_code == 401
