from __future__ import annotations

import ssl
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


def _prepare_async_url(url: str) -> tuple[str, dict]:
    """Strip ssl=require from asyncpg URLs and return it as a connect_arg.

    asyncpg does not accept 'ssl=require' as a query-string param — it needs
    an ssl.SSLContext passed directly via connect_args.  SQLAlchemy passes the
    raw string through, so without this the Neon connection is rejected.
    """
    connect_args: dict = {}
    parsed = urlparse(url)
    if "+asyncpg" in parsed.scheme:
        params = parse_qs(parsed.query, keep_blank_values=True)
        ssl_val = params.pop("ssl", [None])[0]
        if ssl_val in ("require", "true"):
            connect_args["ssl"] = ssl.create_default_context()
        url = urlunparse(parsed._replace(query=urlencode({k: v[0] for k, v in params.items()})))
    return url, connect_args


_db_url, _connect_args = _prepare_async_url(settings.database_url)

engine = create_async_engine(
    _db_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=_connect_args,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
