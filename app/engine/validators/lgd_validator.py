"""LGD (Loss Given Default) upload validator."""

from __future__ import annotations

import pandas as pd

from app.engine.validators.base import (
    ValidationResult,
    check_non_empty_strings,
    check_numeric_range,
    check_required_columns,
    check_uniqueness,
)

LGD_REQUIRED_COLUMNS = [
    "Customer ID",
    "Loan ID",
    "Outstanding Amount",
    "Effective Interest Rate (EIR)",
]

_EIR_ALIASES = ("Effective Interest Rate (EIR)", "Effective Interest Rate", "EIR")


def _resolve_eir_column(df: pd.DataFrame) -> str | None:
    for name in _EIR_ALIASES:
        if name in df.columns:
            return name
    return None


def validate_lgd(
    df: pd.DataFrame,
    *,
    sheet_name: str,
    allowed_collateral_types: set[str],
) -> ValidationResult:
    """Validate an LGD DataFrame against tenant collateral types."""
    result = ValidationResult()

    eir_col = _resolve_eir_column(df)
    required = ["Customer ID", "Loan ID", "Outstanding Amount"]
    if eir_col is not None:
        required.append(eir_col)
    else:
        required.append("Effective Interest Rate (EIR)")

    check_required_columns(df, required, sheet_name=sheet_name, result=result, template_kind="LGD")
    if result.remaining_capacity() == 0:
        return result

    if eir_col is None:
        return result

    known_columns = set(LGD_REQUIRED_COLUMNS) | set(_EIR_ALIASES)
    configured = {name.strip() for name in allowed_collateral_types}
    extra_columns = [
        column
        for column in df.columns
        if column not in known_columns and column not in configured
    ]
    for column in extra_columns[: result.remaining_capacity()]:
        result.add_block(
            title=f"Unknown collateral column: {column} (EC-02)",
            location=f"{sheet_name}, header row, column {column}",
            fix=(
                "Remove this column or add it to your tenant collateral type configuration."
            ),
        )

    check_non_empty_strings(
        df,
        "Customer ID",
        sheet_name=sheet_name,
        result=result,
        title="Customer ID is empty",
        fix="Provide a non-empty Customer ID for every row.",
    )
    check_non_empty_strings(
        df,
        "Loan ID",
        sheet_name=sheet_name,
        result=result,
        title="Loan ID is empty",
        fix="Provide a non-empty Loan ID for every row.",
    )

    check_uniqueness(
        df,
        ["Loan ID"],
        sheet_name=sheet_name,
        result=result,
        title="Duplicate Loan ID",
        fix="Ensure each Loan ID appears only once (duplicate: {key}).",
    )

    check_numeric_range(
        df,
        "Outstanding Amount",
        sheet_name=sheet_name,
        result=result,
        min_value=0.0,
        title="Outstanding Amount must be non-negative",
        fix="Enter an Outstanding Amount greater than or equal to 0 (found {value!r}).",
    )

    check_numeric_range(
        df,
        eir_col,
        sheet_name=sheet_name,
        result=result,
        min_value=0.0,
        max_value=1.0,
        title="EIR must be between 0 and 1 (EC-05)",
        fix="Express EIR as a fraction between 0 and 1, e.g. 0.12 for 12% (found {value!r}).",
    )

    collateral_columns = [column for column in df.columns if column in configured]
    for column in collateral_columns:
        if result.remaining_capacity() == 0:
            break
        check_numeric_range(
            df,
            column,
            sheet_name=sheet_name,
            result=result,
            min_value=0.0,
            title=f"{column} must be non-negative",
            fix=f"Enter a non-negative value for {column} (found {{value!r}}).",
        )

    return result
