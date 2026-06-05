"""Format utility tests."""

from app.engine.format_utils import (
    format_coverage,
    format_file_size,
    map_run_status_to_api,
    short_ulid,
)


def test_short_ulid() -> None:
    assert short_ulid("01ARZ3NDEKTSV4RRFFQ69G5FAV") == "01AR…5FAV"


def test_map_run_status() -> None:
    assert map_run_status_to_api("complete") == "success"
    assert map_run_status_to_api("pd_running") == "running"


def test_format_coverage() -> None:
    assert format_coverage(0.0241) == "2.41%"


def test_format_file_size() -> None:
    assert "MB" in format_file_size(2_500_000)
