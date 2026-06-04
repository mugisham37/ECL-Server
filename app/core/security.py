import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt
from ulid import ULID

from app.config import Settings, get_settings
from app.core.exceptions import ECLException

_ph: PasswordHasher | None = None
_settings: Settings | None = None


def _get_ph() -> PasswordHasher:
    global _ph, _settings
    if _ph is None:
        s = get_settings()
        _settings = s
        _ph = PasswordHasher(
            memory_cost=s.argon2_memory_cost,
            time_cost=s.argon2_time_cost,
            parallelism=s.argon2_parallelism,
        )
    return _ph


def new_ulid() -> str:
    return str(ULID())


def hash_password(plain: str) -> str:
    return _get_ph().hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _get_ph().verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def verify_password_or_dummy(plain: str, hashed: str | None) -> bool:
    """Constant-time-ish: always run verify against real or dummy hash."""
    dummy = "$argon2id$v=19$m=65536,t=3,p=4$ZGVmYXVsdHNhbHQ$RWRlZmF1bHRoYXNo"
    target = hashed if hashed else dummy
    return verify_password(plain, target)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_raw_token(nbytes: int = 64) -> str:
    return secrets.token_urlsafe(nbytes)


def _decode_pem(key_b64: str) -> str:
    import base64

    if key_b64.startswith("-----BEGIN"):
        return key_b64
    return base64.b64decode(key_b64).decode()


def create_access_token(payload: dict[str, Any], settings: Settings | None = None) -> str:
    s = settings or get_settings()
    if not s.jwt_private_key:
        raise ECLException("INTERNAL_ERROR", "JWT keys not configured", 500)
    private_key = _decode_pem(s.jwt_private_key)
    to_encode = payload.copy()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=s.jwt_access_token_expire_minutes)
    to_encode.setdefault("iat", int(now.timestamp()))
    to_encode.setdefault("exp", int(expire.timestamp()))
    to_encode.setdefault("jti", new_ulid())
    return jwt.encode(to_encode, private_key, algorithm=s.jwt_algorithm)


def create_mfa_challenge_token(user_id: str, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    if not s.jwt_private_key:
        raise ECLException("INTERNAL_ERROR", "JWT keys not configured", 500)
    private_key = _decode_pem(s.jwt_private_key)
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "mfa_challenge",
        "jti": new_ulid(),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    return jwt.encode(payload, private_key, algorithm=s.jwt_algorithm)


def encrypt_totp_secret(plaintext: str, settings: Settings | None = None) -> str:
    from cryptography.fernet import Fernet

    s = settings or get_settings()
    if not s.totp_encryption_key:
        raise ECLException("INTERNAL_ERROR", "TOTP encryption key not configured", 500)
    return Fernet(s.totp_encryption_key.encode()).encrypt(plaintext.encode()).decode()


def decrypt_totp_secret(ciphertext: str, settings: Settings | None = None) -> str:
    from cryptography.fernet import Fernet

    s = settings or get_settings()
    if not s.totp_encryption_key:
        raise ECLException("INTERNAL_ERROR", "TOTP encryption key not configured", 500)
    return Fernet(s.totp_encryption_key.encode()).decrypt(ciphertext.encode()).decode()


def generate_backup_codes() -> tuple[list[str], list[dict]]:  # type: ignore[type-arg]
    """Returns (plaintext_codes, argon2-hashed_storage_list). 8 codes, 8-char hex each."""
    ph = _get_ph()
    codes = [secrets.token_hex(4).upper() for _ in range(8)]
    hashed = [{"hash": ph.hash(c), "used": False} for c in codes]
    return codes, hashed


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    s = settings or get_settings()
    if not s.jwt_public_key:
        raise ECLException("TOKEN_INVALID", "JWT keys not configured", 401)
    public_key = _decode_pem(s.jwt_public_key)
    try:
        return jwt.decode(token, public_key, algorithms=[s.jwt_algorithm])
    except JWTError as e:
        msg = str(e).lower()
        if "expired" in msg:
            raise ECLException(
                "TOKEN_EXPIRED", "Access token has expired.", 401
            ) from e
        raise ECLException("TOKEN_INVALID", "Invalid access token.", 401) from e
