"""Async S3/MinIO object storage client."""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from typing import Any, BinaryIO

from aiobotocore.session import AioSession, get_session

from app.config import Settings, get_settings

CHUNK_SIZE = 65536  # 64 KB

_session: AioSession | None = None
_client: Any = None
_client_cm: Any = None


class _HashingReader:
    """Sync file wrapper that computes SHA-256 while streaming."""

    def __init__(self, source: BinaryIO) -> None:
        self._source = source
        self._hasher = hashlib.sha256()
        self.bytes_written = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = CHUNK_SIZE
        chunk = self._source.read(size)
        if chunk:
            self._hasher.update(chunk)
            self.bytes_written += len(chunk)
        return chunk

    @property
    def hex_digest(self) -> str:
        return self._hasher.hexdigest()


def _client_kwargs(settings: Settings) -> dict[str, str | None]:
    kwargs: dict[str, str | None] = {
        "service_name": "s3",
        "aws_access_key_id": settings.storage_access_key,
        "aws_secret_access_key": settings.storage_secret_key,
        "region_name": settings.storage_region,
    }
    if settings.storage_endpoint_url:
        kwargs["endpoint_url"] = settings.storage_endpoint_url
    return kwargs


async def init_storage() -> None:
    """Initialize the shared aiobotocore S3 client."""
    global _session, _client, _client_cm
    if _client is not None:
        return

    settings = get_settings()
    _session = get_session()
    _client_cm = _session.create_client(**_client_kwargs(settings))
    _client = await _client_cm.__aenter__()


async def close_storage() -> None:
    """Close the shared S3 client."""
    global _session, _client, _client_cm
    if _client_cm is not None:
        await _client_cm.__aexit__(None, None, None)
    _session = None
    _client = None
    _client_cm = None


async def get_storage_client() -> Any:
    """Return the singleton S3 client, initializing on first use."""
    if _client is None:
        await init_storage()
    return _client


def build_storage_path(
    tenant_id: str,
    run_id: str,
    subfolder: str,
    filename: str,
) -> str:
    """Build a tenant-scoped object key."""
    return f"/{tenant_id}/runs/{run_id}/{subfolder}/{filename}"


def _normalize_key(key: str) -> str:
    return key.lstrip("/")


async def upload_stream(
    key: str,
    file_obj: BinaryIO | Any,
    content_type: str,
) -> tuple[str, int]:
    """
    Stream *file_obj* to object storage while computing SHA-256 in 64 KB chunks.

    Returns ``(hex_digest, bytes_written)``.
    """
    settings = get_settings()
    client = await get_storage_client()
    reader = _HashingReader(file_obj)

    await client.put_object(
        Bucket=settings.storage_bucket_name,
        Key=_normalize_key(key),
        Body=reader,
        ContentType=content_type,
    )
    return reader.hex_digest, reader.bytes_written


async def download_bytes(key: str) -> bytes:
    """Download an object and return its full contents."""
    settings = get_settings()
    client = await get_storage_client()
    response = await client.get_object(
        Bucket=settings.storage_bucket_name,
        Key=_normalize_key(key),
    )
    async with response["Body"] as body:
        return await body.read()


async def presign_download(key: str, expires_seconds: int = 900) -> str:
    """Return a time-limited presigned GET URL for *key*."""
    settings = get_settings()
    client = await get_storage_client()
    presign: Callable[..., Any] = client.generate_presigned_url
    url = presign(
        "get_object",
        Params={
            "Bucket": settings.storage_bucket_name,
            "Key": _normalize_key(key),
        },
        ExpiresIn=expires_seconds,
    )
    if inspect.isawaitable(url):
        return await url
    return url


async def delete_object(key: str) -> None:
    """Delete an object from storage."""
    settings = get_settings()
    client = await get_storage_client()
    await client.delete_object(
        Bucket=settings.storage_bucket_name,
        Key=_normalize_key(key),
    )
