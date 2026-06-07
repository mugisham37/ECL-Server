import time
import uuid
from collections.abc import Callable

import structlog.contextvars as sctx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.core.logging import get_logger


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        sctx.clear_contextvars()
        sctx.bind_contextvars(request_id=request_id)

        user_id = _try_extract_user_id(request)
        if user_id:
            sctx.bind_contextvars(user_id=user_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            get_logger("app.request").error(
                "request_unhandled_exception",
                method=request.method,
                path=request.url.path,
                elapsed_ms=elapsed_ms,
                exc_info=exc,
            )
            raise

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"

        log = get_logger("app.request")
        level = "warning" if status_code >= 400 else "info"
        getattr(log, level)(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            content_length=request.headers.get("content-length"),
        )

        threshold_ms = getattr(get_settings(), "log_slow_request_ms", 1000)
        if elapsed_ms > threshold_ms:
            log.warning(
                "slow_request",
                method=request.method,
                path=request.url.path,
                elapsed_ms=elapsed_ms,
                threshold_ms=threshold_ms,
            )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        settings = get_settings()
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        if request.url.path.startswith("/api/v1/auth"):
            response.headers["Cache-Control"] = "no-store"
        return response


def _try_extract_user_id(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        from app.core.security import decode_access_token

        payload = decode_access_token(auth[7:])
        return str(payload.get("sub", "")) or None
    except Exception:
        return None
