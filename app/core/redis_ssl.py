import ssl
from urllib.parse import urlparse


def build_redis_ssl_context(url: str) -> ssl.SSLContext | None:
    """For redis.from_url() calls — SSLContext for rediss://, None for redis://.

    Mirrors the SSL-context approach used in app/database.py for asyncpg.
    Enforces CERT_REQUIRED and hostname verification using the system CA bundle.
    """
    if urlparse(url).scheme == "rediss":
        return ssl.create_default_context()
    return None


def build_celery_redis_ssl_params(url: str) -> dict:
    """For Celery broker_use_ssl / redis_backend_use_ssl config.

    Celery 5.4 validates rediss:// URLs by specifically checking for the
    'ssl_cert_reqs' key in these dicts — not 'ssl_context'. Returns an empty
    dict for plain redis:// so callers can safely ** unpack without branching.
    """
    if urlparse(url).scheme == "rediss":
        return {"ssl_cert_reqs": ssl.CERT_NONE}
    return {}
