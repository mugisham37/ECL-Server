"""Shared validation utilities for upload DataFrames."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

MAX_ISSUES = 100

ValidationLevel = Literal["warn", "block"]

STAGING_VALUES = frozenset({"Stage 1", "Stage 2", "Stage 3"})


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    level: ValidationLevel
    title: str
    location: str
    fix: str


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(issue.level == "block" for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.level == "warn" for issue in self.issues)

    def add(self, issue: ValidationIssue) -> None:
        if len(self.issues) >= MAX_ISSUES:
            return
        self.issues.append(issue)

    def add_block(
        self,
        *,
        title: str,
        location: str,
        fix: str,
    ) -> None:
        self.add(ValidationIssue(level="block", title=title, location=location, fix=fix))

    def add_warn(
        self,
        *,
        title: str,
        location: str,
        fix: str,
    ) -> None:
        self.add(ValidationIssue(level="warn", title=title, location=location, fix=fix))

    def remaining_capacity(self) -> int:
        return max(0, MAX_ISSUES - len(self.issues))


def _location(sheet_name: str, row_number: int, column: str) -> str:
    return f"{sheet_name}, row {row_number}, column {column}"


def _excel_row(index: int) -> int:
    """Convert a pandas index to a 1-based Excel row (header on row 1)."""
    return int(index) + 2


def check_required_columns(
    df: pd.DataFrame,
    required: list[str],
    *,
    sheet_name: str,
    result: ValidationResult,
) -> bool:
    """Return True when all required columns are present."""
    missing = [column for column in required if column not in df.columns]
    for column in missing:
        if result.remaining_capacity() == 0:
            return False
        result.add_block(
            title=f"Missing required column: {column}",
            location=f"{sheet_name}, header row",
            fix=f"Add a column named '{column}' to the upload template.",
        )
    return not missing


def check_enum_values(
    df: pd.DataFrame,
    column: str,
    allowed: frozenset[str] | set[str],
    *,
    sheet_name: str,
    result: ValidationResult,
    title: str,
    fix: str,
) -> None:
    if column not in df.columns or result.remaining_capacity() == 0:
        return

    invalid_mask = df[column].notna() & ~df[column].astype(str).str.strip().isin(allowed)
    for index in df.index[invalid_mask][: result.remaining_capacity()]:
        value = df.at[index, column]
        result.add_block(
            title=title,
            location=_location(sheet_name, _excel_row(index), column),
            fix=fix.format(value=value),
        )


def check_numeric_range(
    df: pd.DataFrame,
    column: str,
    *,
    sheet_name: str,
    result: ValidationResult,
    min_value: float | None = None,
    max_value: float | None = None,
    title: str,
    fix: str,
    allow_missing: bool = False,
) -> None:
    if column not in df.columns or result.remaining_capacity() == 0:
        return

    numeric = pd.to_numeric(df[column], errors="coerce")
    invalid_mask = (
        df[column].notna() & numeric.isna() if allow_missing else numeric.isna()
    )

    if min_value is not None:
        invalid_mask |= numeric.notna() & (numeric < min_value)
    if max_value is not None:
        invalid_mask |= numeric.notna() & (numeric > max_value)

    for index in df.index[invalid_mask][: result.remaining_capacity()]:
        value = df.at[index, column]
        result.add_block(
            title=title,
            location=_location(sheet_name, _excel_row(index), column),
            fix=fix.format(value=value),
        )


def check_non_empty_strings(
    df: pd.DataFrame,
    column: str,
    *,
    sheet_name: str,
    result: ValidationResult,
    title: str,
    fix: str,
) -> None:
    if column not in df.columns or result.remaining_capacity() == 0:
        return

    empty_mask = df[column].isna() | df[column].astype(str).str.strip().eq("")
    for index in df.index[empty_mask][: result.remaining_capacity()]:
        result.add_block(
            title=title,
            location=_location(sheet_name, _excel_row(index), column),
            fix=fix,
        )


def check_valid_dates(
    df: pd.DataFrame,
    column: str,
    *,
    sheet_name: str,
    result: ValidationResult,
    title: str,
    fix: str,
) -> pd.Series | None:
    if column not in df.columns or result.remaining_capacity() == 0:
        return None

    parsed = pd.to_datetime(df[column], errors="coerce")
    invalid_mask = df[column].notna() & parsed.isna()
    for index in df.index[invalid_mask][: result.remaining_capacity()]:
        value = df.at[index, column]
        result.add_block(
            title=title,
            location=_location(sheet_name, _excel_row(index), column),
            fix=fix.format(value=value),
        )
    return parsed


def check_uniqueness(
    df: pd.DataFrame,
    columns: list[str],
    *,
    sheet_name: str,
    result: ValidationResult,
    title: str,
    fix: str,
) -> None:
    if result.remaining_capacity() == 0:
        return
    if any(column not in df.columns for column in columns):
        return

    duplicate_mask = df.duplicated(subset=columns, keep=False)
    for index in df.index[duplicate_mask][: result.remaining_capacity()]:
        key_values = ", ".join(f"{column}={df.at[index, column]!r}" for column in columns)
        result.add_block(
            title=title,
            location=_location(sheet_name, _excel_row(index), columns[0]),
            fix=fix.format(key=key_values),
        )


def check_allowed_set_membership(
    df: pd.DataFrame,
    column: str,
    allowed: frozenset[str] | set[str],
    *,
    sheet_name: str,
    result: ValidationResult,
    title: str,
    fix: str,
) -> None:
    """Block when values are not in the tenant-configured allowed set."""
    check_enum_values(
        df,
        column,
        allowed,
        sheet_name=sheet_name,
        result=result,
        title=title,
        fix=fix,
    )


def check_enum_values_grouped(
    df: pd.DataFrame,
    column: str,
    allowed: frozenset[str] | set[str],
    *,
    sheet_name: str,
    result: ValidationResult,
    title: str,
    fix: str,
) -> None:
    """Like check_enum_values but emits one issue per unique bad value (not one per row)."""
    if column not in df.columns or result.remaining_capacity() == 0:
        return

    invalid_mask = df[column].notna() & ~df[column].astype(str).str.strip().isin(allowed)
    if not invalid_mask.any():
        return

    for value, group in df[invalid_mask].groupby(df[column]):
        if result.remaining_capacity() == 0:
            break
        count = len(group)
        result.add_block(
            title=title,
            location=f"{sheet_name}, column {column} ({count} row{'s' if count != 1 else ''})",
            fix=fix.format(value=value),
        )
