"""Cross-file validation for PD, LGD, and EAD uploads on the same run."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.engine.validators.base import ValidationIssue, ValidationResult

_EIR_ALIASES = ("Effective Interest Rate (EIR)", "Effective Interest Rate", "EIR")
_EIR_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class CrossFileData:
    pd_combined: pd.DataFrame
    lgd_combined: pd.DataFrame
    ead_combined: pd.DataFrame
    ead_upload_id: str | None
    ead_filename: str | None
    lgd_upload_id: str | None
    lgd_filename: str | None
    pd_upload_id: str | None
    pd_filename: str | None


def _loan_ids(df: pd.DataFrame) -> set[str]:
    if df.empty or "Loan ID" not in df.columns:
        return set()
    return {
        str(value).strip()
        for value in df["Loan ID"].dropna().astype(str)
        if str(value).strip()
    }


def _resolve_eir_column(df: pd.DataFrame) -> str | None:
    for name in _EIR_ALIASES:
        if name in df.columns:
            return name
    return None


def _eir_by_loan(df: pd.DataFrame) -> dict[str, float]:
    col = _resolve_eir_column(df)
    if col is None or "Loan ID" not in df.columns:
        return {}
    mapping: dict[str, float] = {}
    for _, row in df.iterrows():
        loan_id = str(row["Loan ID"]).strip()
        if not loan_id:
            continue
        try:
            mapping[loan_id] = float(row[col])
        except (TypeError, ValueError):
            continue
    return mapping


def _segments_with_pd(pd_df: pd.DataFrame) -> set[str]:
    if pd_df.empty or "SEGMENT" not in pd_df.columns:
        return set()
    return {
        str(value).strip()
        for value in pd_df["SEGMENT"].dropna().astype(str)
        if str(value).strip()
    }


def _ead_segments(ead_df: pd.DataFrame) -> set[str]:
    if ead_df.empty or "SEGMENT" not in ead_df.columns:
        return set()
    return {
        str(value).strip()
        for value in ead_df["SEGMENT"].dropna().astype(str)
        if str(value).strip()
    }


def validate_cross_files(data: CrossFileData) -> list[ValidationIssue]:
    """Return cross-file validation issues (not tied to a single sheet row)."""
    result = ValidationResult()
    ead_loans = _loan_ids(data.ead_combined)
    lgd_loans = _loan_ids(data.lgd_combined)
    pd_loans = _loan_ids(data.pd_combined)

    missing_from_lgd = sorted(ead_loans - lgd_loans)
    if missing_from_lgd:
        sample = ", ".join(missing_from_lgd[:5])
        suffix = f" (and {len(missing_from_lgd) - 5} more)" if len(missing_from_lgd) > 5 else ""
        result.add_block(
            title=f"{len(missing_from_lgd)} EAD loan(s) missing from LGD file (EC-06)",
            location="Cross-file check",
            fix=(
                f"Every Loan ID in your EAD file must also appear in the LGD file. "
                f"Missing examples: {sample}{suffix}."
            ),
        )

    missing_from_pd = sorted(ead_loans - pd_loans)
    if missing_from_pd:
        sample = ", ".join(missing_from_pd[:5])
        suffix = f" (and {len(missing_from_pd) - 5} more)" if len(missing_from_pd) > 5 else ""
        result.add_warn(
            title=f"{len(missing_from_pd)} EAD loan(s) have no PD history",
            location="Cross-file check",
            fix=(
                f"These loans appear in EAD but not in PD: {sample}{suffix}. "
                "Add PD rows for them or remove them from EAD."
            ),
        )

    ead_segments = _ead_segments(data.ead_combined)
    pd_segments = _segments_with_pd(data.pd_combined)
    missing_segments = sorted(ead_segments - pd_segments)
    if missing_segments:
        result.add_block(
            title=f"No PD history for segment(s): {', '.join(missing_segments)} (EC-08)",
            location="Cross-file check",
            fix=(
                "Every segment in your EAD file must have corresponding PD data. "
                "Add these segments to your PD file and re-upload."
            ),
        )

    lgd_eir = _eir_by_loan(data.lgd_combined)
    ead_eir = _eir_by_loan(data.ead_combined)
    mismatched: list[str] = []
    for loan_id in sorted(ead_loans & lgd_loans):
        if loan_id not in lgd_eir or loan_id not in ead_eir:
            continue
        if abs(lgd_eir[loan_id] - ead_eir[loan_id]) > _EIR_TOLERANCE:
            mismatched.append(loan_id)
    if mismatched:
        sample = ", ".join(mismatched[:5])
        suffix = f" (and {len(mismatched) - 5} more)" if len(mismatched) > 5 else ""
        result.add_warn(
            title=f"EIR mismatch between LGD and EAD for {len(mismatched)} loan(s)",
            location="Cross-file check",
            fix=(
                f"Effective Interest Rate should match between LGD and EAD for the same Loan ID. "
                f"Affected examples: {sample}{suffix}. LGD values take precedence at compute time."
            ),
        )

    return result.issues
