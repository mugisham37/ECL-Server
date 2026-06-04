from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

_settings = get_settings()
limiter = Limiter(
    key_func=get_remote_address,
    enabled=_settings.rate_limit_enabled,
    storage_uri=_settings.redis_url if _settings.rate_limit_enabled else "memory://",
)
