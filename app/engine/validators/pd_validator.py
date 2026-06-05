"""PD (Probability of Default) upload validator."""

from __future__ import annotations

import pandas as pd

from app.engine.validators.base import (
    STAGING_VALUES,
    ValidationResult,
    check_enum_values,
    check_non_empty_strings,
    check_numeric_range,
    check_required_columns,
    check_uniqueness,
    check_valid_dates,
)

_REPORTING_MONTH_ALIASES = ("Reporting Month", 'Reporting Month ("As At")', "As At")


def _resolve_reporting_month_column(df: pd.DataFrame) -> str | None:
    for name in _REPORTING_MONTH_ALIASES:
        if name in df.columns:
            return name
    return None


def validate_pd(
    df: pd.DataFrame,
    *,
    sheet_name: str,
    allowed_segments: set[str],
) -> ValidationResult:
    """Validate a PD DataFrame against tenant segments and PD data contract rules."""
    result = ValidationResult()

    reporting_col = _resolve_reporting_month_column(df)
    required = ["Loan ID", "Staging", "Loan Amount", "SEGMENT"]
    if reporting_col is not None:
        required.append(reporting_col)
    else:
        required.append("Reporting Month")

    check_required_columns(df, required, sheet_name=sheet_name, result=result)
    if result.remaining_capacity() == 0:
        return result

    if reporting_col is None:
        return result

    check_non_empty_strings(
        df,
        "Loan ID",
        sheet_name=sheet_name,
        result=result,
        title="Loan ID is empty",
        fix="Provide a non-empty Loan ID for every row.",
    )
    check_non_empty_strings(
        df,
        "SEGMENT",
        sheet_name=sheet_name,
        result=result,
        title="SEGMENT is empty",
        fix="Provide a non-empty SEGMENT for every row.",
    )

    check_valid_dates(
        df,
        reporting_col,
        sheet_name=sheet_name,
        result=result,
        title="Reporting Month is not a valid date",
        fix="Use a valid date for Reporting Month (found {value!r}).",
    )

    check_enum_values(
        df,
        "Staging",
        STAGING_VALUES,
        sheet_name=sheet_name,
        result=result,
        title="Invalid Staging value",
        fix='Use exactly one of "Stage 1", "Stage 2", or "Stage 3" (found {value!r}).',
    )

    check_numeric_range(
        df,
        "Loan Amount",
        sheet_name=sheet_name,
        result=result,
        min_value=0.0,
        title="Loan Amount must be non-negative",
        fix="Enter a Loan Amount greater than or equal to 0 (found {value!r}).",
    )

    if allowed_segments:
        check_enum_values(
            df,
            "SEGMENT",
            {segment.strip() for segment in allowed_segments},
            sheet_name=sheet_name,
            result=result,
            title="SEGMENT is not configured for this tenant",
            fix="Use a segment from your tenant configuration (found {value!r}).",
        )

    duplicate_columns = ["Loan ID", reporting_col]
    check_uniqueness(
        df,
        duplicate_columns,
        sheet_name=sheet_name,
        result=result,
        title="Duplicate Loan ID and Reporting Month (EC-10)",
        fix="Remove duplicate rows for {key}.",
    )

    return result
