import hashlib
import re

import httpx

from app.config import get_settings

FORBIDDEN_DEFAULT = ("ecl", "platform")


async def check_password_pwned(password: str) -> bool:
    """Return True if password appears in HIBP (breached)."""
    settings = get_settings()
    if not settings.hibp_enabled:
        return False
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    url = f"https://api.pwnedpasswords.com/range/{prefix}"
    try:
        async with httpx.AsyncClient(timeout=settings.hibp_timeout_seconds) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        for line in resp.text.splitlines():
            hash_suffix, count = line.split(":")
            if hash_suffix == suffix and int(count) > 0:
                return True
        return False
    except Exception:
        return False


def validate_password_strength(
    password: str,
    name: str | None = None,
    org_name: str | None = None,
) -> list[str]:
    """Return list of violated rule codes (empty = valid)."""
    violations: list[str] = []
    if len(password) < 8:
        violations.append("PASSWORD_TOO_SHORT")
    if not (re.search(r"[a-zA-Z]", password) and re.search(r"[0-9]", password)):
        violations.append("PASSWORD_MISSING_MIX")

    forbidden: list[str] = list(FORBIDDEN_DEFAULT)
    if name:
        for part in name.split():
            if len(part) > 2:
                forbidden.append(part.lower())
    if org_name:
        for part in org_name.split():
            if len(part) > 2:
                forbidden.append(part.lower())

    pw_lower = password.lower()
    for term in forbidden:
        if term and len(term) > 2 and term in pw_lower:
            violations.append("PASSWORD_CONTAINS_FORBIDDEN")
            break

    return violations


async def validate_password_full(
    password: str,
    name: str | None = None,
    org_name: str | None = None,
) -> list[str]:
    violations = validate_password_strength(password, name, org_name)
    if not violations and await check_password_pwned(password):
        violations.append("PASSWORD_PWNED")
    return violations
