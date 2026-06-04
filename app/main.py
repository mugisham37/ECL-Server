import base64
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.limiter import limiter
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.database import engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()
    from app.core.cache import close_redis

    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    register_exception_handlers(app)

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
        expose_headers=["X-Request-ID", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
        max_age=600,
    )

    try:
        from starlette_csrf import CSRFMiddleware

        app.add_middleware(
            CSRFMiddleware,
            secret=settings.csrf_secret,
            sensitive_cookies={settings.refresh_cookie_name},
            cookie_name="csrftoken",
            cookie_path="/",
            cookie_secure=settings.is_production,
            cookie_samesite="lax",
            header_name="x-csrf-token",
            exempt_urls=[
                r"^/health$",
                r"^/ready$",
                r"^/\.well-known/",
                r"^/api/v1/auth/login$",
                r"^/api/v1/auth/register$",
                r"^/api/v1/auth/forgot-password$",
                r"^/api/v1/auth/reset-password$",
                r"^/api/v1/auth/verify-email/",
                r"^/api/v1/auth/mfa/verify$",
                r"^/api/v1/invites/validate/",
                r"^/api/v1/invites/accept$",
                r"^/docs",
                r"^/openapi",
                r"^/metrics",
            ],
        )
    except ImportError:
        pass  # starlette-csrf not installed yet; skips gracefully

    from app.routers import api_router

    app.include_router(api_router)

    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(
            app,
            endpoint="/metrics",
            include_in_schema=False,
            should_gzip=True,
        )
    except Exception:
        pass  # metrics optional if deps missing

    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            release=settings.release,
            integrations=[FastApiIntegration()],
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        db_ok = "ok"
        redis_ok = "ok"
        try:
            from sqlalchemy import text

            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            db_ok = "error"
        try:
            from app.core.cache import get_redis_client

            redis = await get_redis_client()
            await redis.ping()
        except Exception:
            redis_ok = "error"
        return {
            "status": "ok" if db_ok == "ok" and redis_ok == "ok" else "degraded",
            "db": db_ok,
            "redis": redis_ok,
            "version": settings.app_version,
        }

    @app.get("/ready", response_model=None)
    async def ready() -> JSONResponse | dict[str, str]:
        try:
            from sqlalchemy import text

            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready"})

    @app.get("/.well-known/jwks.json", include_in_schema=False)
    async def jwks() -> JSONResponse:
        if not settings.jwt_public_key:
            return JSONResponse(content={"keys": []})
        pem = settings.jwt_public_key
        if not pem.startswith("-----BEGIN"):
            pem = base64.b64decode(pem).decode()
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        key = load_pem_public_key(pem.encode())
        numbers = key.public_numbers()
        n = base64.urlsafe_b64encode(
            numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
        ).rstrip(b"=").decode()
        e = base64.urlsafe_b64encode(
            numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
        ).rstrip(b"=").decode()
        return JSONResponse(
            content={
                "keys": [
                    {
                        "kty": "RSA",
                        "use": "sig",
                        "alg": settings.jwt_algorithm,
                        "kid": settings.jwt_key_id,
                        "n": n,
                        "e": e,
                    }
                ]
            },
            headers={"Cache-Control": "max-age=3600"},
        )

    return app


app = create_app()
