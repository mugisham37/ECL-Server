import ssl
from urllib.parse import urlparse


def build_redis_connection_kwargs(url: str) -> dict:
    """For redis-py from_url() calls — returns SSL kwargs for rediss://, {} for redis://.

    redis-py ≥ 5.0 does not accept ssl_context as a kwarg to from_url(); instead
    pass ssl_cert_reqs directly. Upstash Redis uses a valid cert but requires
    CERT_NONE to avoid hostname-verification failures on managed Redis endpoints.
    """
    if urlparse(url).scheme == "rediss":
        return {"ssl_cert_reqs": "none"}
    return {}


# Kept for backwards-compatibility in case any code still imports this name.
def build_redis_ssl_context(url: str) -> None:  # type: ignore[return]
    """Deprecated — use build_redis_connection_kwargs instead."""
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
