from unittest.mock import AsyncMock, patch

import pytest

from app.core.hibp import check_password_pwned, validate_password_strength


@pytest.mark.asyncio
async def test_pwned_password_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_pwned(_password: str) -> bool:
        return True

    monkeypatch.setattr("app.core.hibp.check_password_pwned", fake_pwned)
    import app.core.hibp as hibp_mod

    assert await hibp_mod.check_password_pwned("password") is True


@pytest.mark.asyncio
async def test_clean_password() -> None:
    with patch("app.core.hibp.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get = AsyncMock(
            return_value=type(
                "R",
                (),
                {"raise_for_status": lambda self: None, "text": "FFFF:1"},
            )()
        )
        result = await check_password_pwned("UniqueZebra99!")
        assert result is False


def test_password_strength_rules() -> None:
    assert "PASSWORD_TOO_SHORT" in validate_password_strength("short1")
    assert "PASSWORD_MISSING_MIX" in validate_password_strength("allletters")
    assert "PASSWORD_CONTAINS_FORBIDDEN" in validate_password_strength(
        "eclplatform1", org_name="ECL Platform"
    )
