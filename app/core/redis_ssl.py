import ssl
from urllib.parse import urlparse


def build_redis_ssl_context(url: str) -> ssl.SSLContext | None:
    """Return a maximum-security SSLContext for rediss:// URLs, None otherwise.

    Mirrors the SSL-context approach used in app/database.py for asyncpg.
    The returned context enforces CERT_REQUIRED and hostname verification
    using the system CA bundle.
    """
    if urlparse(url).scheme == "rediss":
        return ssl.create_default_context()
    return None
