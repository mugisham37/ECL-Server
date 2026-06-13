"""EAD (Exposure at Default) upload validator."""

from __future__ import annotations

import pandas as pd

from app.engine.validators.base import (
    STAGING_VALUES,
    ValidationResult,
    _excel_row,
    _location,
    check_enum_values,
    check_enum_values_grouped,
    check_non_empty_strings,
    check_numeric_range,
    check_required_columns,
    check_uniqueness,
    check_valid_dates,
)

DEFAULT_REPAYMENT_FREQUENCIES = frozenset({"MTH", "QTR"})

_STAGING_ALIASES = ("Staging", "Staging (Stage)")
_EIR_ALIASES = ("Effective Interest Rate", "Effective Interest Rate (EIR)", "EIR")


def _resolve_column(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def validate_ead(
    df: pd.DataFrame,
    *,
    sheet_name: str,
    allowed_segments: set[str],
    allowed_repayment_frequencies: set[str] | frozenset[str] | None = None,
) -> ValidationResult:
    """Validate an EAD DataFrame including EC-03, EC-04, EC-05, and EC-09 rules."""
    result = ValidationResult()
    frequencies = allowed_repayment_frequencies or DEFAULT_REPAYMENT_FREQUENCIES

    staging_col = _resolve_column(df, _STAGING_ALIASES)
    eir_col = _resolve_column(df, _EIR_ALIASES)

    required = [
        "Loan ID",
        "Customer ID",
        "SEGMENT",
        "Reporting Date",
        "Maturity Date",
        "Adjusted Maturity Date",
        "First Payment Date",
        "Outstanding Amount",
        "Repayment Frequency",
    ]
    required.append(staging_col if staging_col is not None else "Staging")
    required.append(eir_col if eir_col is not None else "Effective Interest Rate")

    check_required_columns(df, required, sheet_name=sheet_name, result=result)
    if result.remaining_capacity() == 0:
        return result

    if staging_col is None or eir_col is None:
        return result

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

    reporting_dates = check_valid_dates(
        df,
        "Reporting Date",
        sheet_name=sheet_name,
        result=result,
        title="Reporting Date is not a valid date",
        fix="Use a valid Reporting Date (found {value!r}).",
    )
    maturity_dates = check_valid_dates(
        df,
        "Maturity Date",
        sheet_name=sheet_name,
        result=result,
        title="Maturity Date is not a valid date",
        fix="Use a valid Maturity Date (found {value!r}).",
    )
    first_payment_dates = check_valid_dates(
        df,
        "First Payment Date",
        sheet_name=sheet_name,
        result=result,
        title="First Payment Date is not a valid date",
        fix="Use a valid First Payment Date (found {value!r}).",
    )
    adjusted_maturity_dates = check_valid_dates(
        df,
        "Adjusted Maturity Date",
        sheet_name=sheet_name,
        result=result,
        title="Adjusted Maturity Date is not a valid date",
        fix="Use a valid Adjusted Maturity Date (found {value!r}).",
    )

    check_enum_values(
        df,
        staging_col,
        STAGING_VALUES,
        sheet_name=sheet_name,
        result=result,
        title="Invalid Staging value",
        fix='Use exactly one of "Stage 1", "Stage 2", or "Stage 3" (found {value!r}).',
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
        fix="Express EIR as a fraction between 0 and 1 (found {value!r}).",
    )

    if allowed_segments:
        check_enum_values_grouped(
            df,
            "SEGMENT",
            {segment.strip() for segment in allowed_segments},
            sheet_name=sheet_name,
            result=result,
            title="SEGMENT is not configured for this tenant",
            fix="Use a segment from your tenant configuration (found {value!r}).",
        )

    if "Repayment Frequency" in df.columns and result.remaining_capacity() > 0:
        freq_allowed = {freq.strip().upper() for freq in frequencies}
        normalized = df["Repayment Frequency"].astype(str).str.strip().str.upper()
        invalid_mask = df["Repayment Frequency"].notna() & ~normalized.isin(freq_allowed)
        for index in df.index[invalid_mask][: result.remaining_capacity()]:
            value = df.at[index, "Repayment Frequency"]
            result.add_block(
                title="Unsupported Repayment Frequency (EC-09)",
                location=_location(sheet_name, _excel_row(index), "Repayment Frequency"),
                fix=(
                    "Use a supported repayment frequency such as MTH or QTR "
                    f"(found {value!r})."
                ),
            )

    if (
        reporting_dates is not None
        and maturity_dates is not None
        and result.remaining_capacity() > 0
    ):
        ec03_mask = (
            reporting_dates.notna()
            & maturity_dates.notna()
            & (maturity_dates < reporting_dates)
        )
        for index in df.index[ec03_mask][: result.remaining_capacity()]:
            result.add_block(
                title="Maturity Date is before Reporting Date (EC-03)",
                location=_location(sheet_name, _excel_row(index), "Maturity Date"),
                fix="Set Maturity Date on or after Reporting Date.",
            )

    if (
        reporting_dates is not None
        and first_payment_dates is not None
        and result.remaining_capacity() > 0
    ):
        ec04_mask = (
            reporting_dates.notna()
            & first_payment_dates.notna()
            & (first_payment_dates > reporting_dates)
        )
        for index in df.index[ec04_mask][: result.remaining_capacity()]:
            result.add_block(
                title="First Payment Date is after Reporting Date (EC-04)",
                location=_location(sheet_name, _excel_row(index), "First Payment Date"),
                fix="Set First Payment Date on or before Reporting Date.",
            )

    if (
        first_payment_dates is not None
        and adjusted_maturity_dates is not None
        and result.remaining_capacity() > 0
    ):
        adj_mask = (
            first_payment_dates.notna()
            & adjusted_maturity_dates.notna()
            & (adjusted_maturity_dates < first_payment_dates)
        )
        for index in df.index[adj_mask][: result.remaining_capacity()]:
            result.add_block(
                title="Adjusted Maturity Date is before First Payment Date",
                location=_location(sheet_name, _excel_row(index), "Adjusted Maturity Date"),
                fix="Set Adjusted Maturity Date on or after First Payment Date.",
            )

    return result
