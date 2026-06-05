"""Tests for async S3/MinIO storage client."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import socket
from typing import TYPE_CHECKING

import pytest

from app.config import get_settings
from app.core import storage as storage_module
from app.core.storage import (
    build_storage_path,
    close_storage,
    delete_object,
    download_bytes,
    init_storage,
    presign_download,
    upload_stream,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def test_build_storage_path() -> None:
    path = build_storage_path("tenant01", "run01", "uploads", "pd_data.xlsx")
    assert path == "/tenant01/runs/run01/uploads/pd_data.xlsx"


def _minio_reachable(host: str = "localhost", port: int = 9000, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def _ensure_bucket() -> None:
    settings = get_settings()
    client = await storage_module.get_storage_client()
    try:
        await client.head_bucket(Bucket=settings.storage_bucket_name)
    except Exception:
        await client.create_bucket(Bucket=settings.storage_bucket_name)


@pytest.fixture
async def storage_backend() -> AsyncIterator[str]:
    """Use moto when installed, otherwise real MinIO; skip when neither is available."""
    await close_storage()

    if importlib.util.find_spec("moto") is not None:
        from moto import mock_aws

        settings = get_settings()

        class _MotoSettings:
            storage_endpoint_url = ""
            storage_access_key = "testing"
            storage_secret_key = "testing"
            storage_bucket_name = settings.storage_bucket_name
            storage_region = settings.storage_region

        original_get_settings = storage_module.get_settings

        with mock_aws():
            import aiobotocore.session

            session = aiobotocore.session.get_session()
            async with session.create_client(
                "s3",
                region_name=settings.storage_region,
                aws_access_key_id="testing",
                aws_secret_access_key="testing",
            ) as client:
                await client.create_bucket(Bucket=settings.storage_bucket_name)

            storage_module.get_settings = lambda: _MotoSettings()  # type: ignore[assignment]
            try:
                yield "moto"
            finally:
                storage_module.get_settings = original_get_settings
                await close_storage()
        return

    if not _minio_reachable():
        pytest.skip("Neither moto nor MinIO is available")

    await init_storage()
    await _ensure_bucket()
    try:
        yield "minio"
    finally:
        await close_storage()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upload_download_presign_delete(storage_backend: str) -> None:
    key = build_storage_path("tenant-test", "run-test", "uploads", "sample.txt")
    payload = b"ecl storage integration test\n"
    digest_expected = hashlib.sha256(payload).hexdigest()

    file_obj = io.BytesIO(payload)
    digest, bytes_written = await upload_stream(key, file_obj, "text/plain")
    assert digest == digest_expected
    assert bytes_written == len(payload)

    downloaded = await download_bytes(key)
    assert downloaded == payload

    url = await presign_download(key, expires_seconds=300)
    assert isinstance(url, str)
    assert len(url) > 0

    await delete_object(key)

    from botocore.exceptions import ClientError

    with pytest.raises(ClientError):
        await download_bytes(key)
