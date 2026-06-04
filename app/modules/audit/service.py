import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.security import new_ulid
from app.modules.audit.models import AuditLog


async def log_event(
    db: AsyncSession,
    event_type: str,
    *,
    user_id: str | None = None,
    status: str = "success",
    error_code: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    details: dict | None = None,  # type: ignore[type-arg]
    settings: Settings | None = None,
) -> None:
    """Append an audit log entry. Never raises — audit failures must not block the caller."""
    try:
        s = settings or get_settings()
        salt = s.ip_hash_salt
        ip_hash = (
            hashlib.sha256(f"{ip}{salt}".encode()).hexdigest() if ip else None
        )
        ua_hash = (
            hashlib.sha256(f"{user_agent}{salt}".encode()).hexdigest() if user_agent else None
        )
        entry = AuditLog(
            id=new_ulid(),
            user_id=user_id,
            event_type=event_type,
            status=status,
            ip_address_hash=ip_hash,
            user_agent_hash=ua_hash,
            details=details,
            error_code=error_code,
        )
        db.add(entry)
    except Exception:  # noqa: BLE001
        pass
