from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_settings
from app.core.exceptions import ECLException
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_hash_verify_password() -> None:
    hashed = hash_password("TestPass123!")
    assert verify_password("TestPass123!", hashed)
    assert not verify_password("wrong", hashed)


def test_hash_token_deterministic() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("xyz")


def test_jwt_round_trip() -> None:
    payload = {
        "sub": "01USER",
        "email": "a@b.com",
        "name": "Test",
        "role": "administrator",
        "tenant_id": "01TENANT",
    }
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded["sub"] == "01USER"
    assert decoded["email"] == "a@b.com"


def test_expired_jwt_raises() -> None:
    settings = get_settings()
    payload = {
        "sub": "x",
        "email": "a@b.com",
        "name": "T",
        "role": "administrator",
        "tenant_id": "t",
        "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
    }
    token = create_access_token(payload, settings)
    with pytest.raises(ECLException) as exc:
        decode_access_token(token)
    assert exc.value.code == "TOKEN_EXPIRED"
