import hashlib
import re
import unicodedata

from user_agents import parse as parse_ua

from app.core.enums import DeviceType
from app.core.security import new_ulid


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text or "workspace"


async def unique_slug(base: str, existing: set[str]) -> str:
    slug = slugify(base)
    if slug not in existing:
        return slug
    for i in range(2, 1000):
        candidate = f"{slug}-{i}"
        if candidate not in existing:
            return candidate
    return f"{slug}-{new_ulid()[:8].lower()}"


def user_initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else "??"


def parse_device(user_agent: str | None) -> tuple[str, str | None, str | None]:
    if not user_agent:
        return DeviceType.UNKNOWN.value, None, None
    ua = parse_ua(user_agent)
    device_type = DeviceType.PHONE.value if ua.is_mobile else DeviceType.LAPTOP.value
    browser = f"{ua.browser.family} on {ua.os.family}"
    return device_type, browser, ua.browser.family


def hash_ip(ip: str, secret: str) -> str:
    return hashlib.sha256(f"{secret}:{ip}".encode()).hexdigest()
