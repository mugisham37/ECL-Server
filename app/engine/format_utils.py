"""Formatting helpers for API responses and run metadata."""

from __future__ import annotations

from app.core.run_enums import RunStatus

_RUNNING_STATUSES = frozenset(
    {
        RunStatus.PD_RUNNING.value,
        RunStatus.LGD_RUNNING.value,
        RunStatus.EAD_RUNNING.value,
    }
)

_STATUS_MAP: dict[str, str] = {
    RunStatus.COMPLETE.value: "success",
    RunStatus.DRAFT.value: "draft",
    RunStatus.DELETED.value: "deleted",
    RunStatus.FAILED.value: "failed",
    RunStatus.QUEUED.value: "queued",
}


def short_ulid(ulid: str) -> str:
    """Return a truncated ULID for display (first 4 + ellipsis + last 4)."""
    if len(ulid) <= 8:
        return ulid
    return f"{ulid[:4]}\u2026{ulid[-4:]}"


def format_file_size(num_bytes: int) -> str:
    """Format a byte count as a human-readable size string."""
    if num_bytes < 0:
        msg = "byte count must be non-negative"
        raise ValueError(msg)
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024**2:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024**3:
        return f"{num_bytes / 1024**2:.1f} MB"
    return f"{num_bytes / 1024**3:.1f} GB"


def format_coverage(ratio: float) -> str:
    """Format a coverage ratio (ECL / outstanding) as a percentage string."""
    return f"{ratio * 100:.2f}%"


def map_run_status_to_api(db_status: str) -> str:
    """Map internal run status values to frontend RunDetailStatus strings."""
    if db_status in _RUNNING_STATUSES:
        return "running"
    return _STATUS_MAP.get(db_status, db_status)
