"""PD (Probability of Default) computation engine."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.linalg import matrix_power

STAGES = ("Stage 1", "Stage 2", "Stage 3")
NEXT_STAGES = (*STAGES, "Offbooks")
MAX_PD_MONTH = 299
_DENOM_EPS = 1e-15

_REPORTING_MONTH_ALIASES = ("Reporting Month", 'Reporting Month ("As At")', "As At")


def _resolve_reporting_month_column(df: pd.DataFrame) -> str:
    for name in _REPORTING_MONTH_ALIASES:
        if name in df.columns:
            return name
    return "Reporting Month"


def _matrix_to_dict(matrix: np.ndarray) -> dict[str, list[float]]:
    return {
        stage: [float(matrix[row_idx, col_idx]) for col_idx in range(3)]
        for row_idx, stage in enumerate(STAGES)
    }


def _build_monthly_matrix(subset: pd.DataFrame) -> np.ndarray:
    pivot = subset.pivot_table(
        index="Staging",
        columns="Next Month Staging",
        values="Loan Amount",
        aggfunc="sum",
        fill_value=0.0,
    )
    matrix = np.zeros((3, 4), dtype=np.float64)
    for row_idx, stage in enumerate(STAGES):
        if stage not in pivot.index:
            continue
        for col_idx, next_stage in enumerate(NEXT_STAGES):
            if next_stage in pivot.columns:
                matrix[row_idx, col_idx] = float(pivot.loc[stage, next_stage])
    return matrix[:, :3]


def _row_proportions(matrix: np.ndarray) -> np.ndarray:
    proportions = np.zeros_like(matrix, dtype=np.float64)
    for row_idx in range(3):
        row_total = matrix[row_idx].sum()
        if row_total > 0:
            proportions[row_idx] = matrix[row_idx] / row_total
    return proportions


def _normalize_matrix(proportions: np.ndarray) -> np.ndarray:
    normalized = proportions.copy()
    normalized[0] = [proportions[0, 0], proportions[0, 1] + proportions[0, 2], 0.0]
    normalized[2] = [0.0, 0.0, 1.0]
    return normalized


def _compute_marginal_pd(group: pd.DataFrame) -> pd.Series:
    s3 = group["Stage_3_prob"].to_numpy(dtype=np.float64)
    marginal = np.zeros(len(s3), dtype=np.float64)
    if len(s3) == 0:
        return pd.Series(marginal, index=group.index)
    marginal[0] = s3[0]
    for idx in range(1, len(s3)):
        denom = 1.0 - s3[idx - 1]
        if denom <= _DENOM_EPS:
            marginal[idx] = 0.0
        else:
            marginal[idx] = (s3[idx] - s3[idx - 1]) / denom
    return pd.Series(marginal, index=group.index)


def compute_pd(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float], dict[str, Any]]:
    """Run the 11-step PD computation pipeline.

    Returns the long-form PD table, cure rates per segment, and intermediate
    matrices for Excel export.
    """
    working = df.copy()
    reporting_col = _resolve_reporting_month_column(working)
    if reporting_col != "Reporting Month":
        working = working.rename(columns={reporting_col: "Reporting Month"})

    # Step 1 — combine/sort (caller combines files; dedupe and sort here).
    working["Reporting Month"] = pd.to_datetime(working["Reporting Month"])
    working = working.drop_duplicates(subset=["Loan ID", "Reporting Month"], keep="first")
    working = working.sort_values(["Loan ID", "Reporting Month"], kind="mergesort").reset_index(
        drop=True
    )

    # Step 2 — next month staging.
    next_lookup = working[["Loan ID", "Reporting Month", "Staging"]].copy()
    next_lookup["Reporting Month"] = next_lookup["Reporting Month"] - pd.DateOffset(months=1)
    working = working.merge(
        next_lookup.rename(columns={"Staging": "Next Month Staging"}),
        on=["Loan ID", "Reporting Month"],
        how="left",
    )
    working["Next Month Staging"] = working["Next Month Staging"].fillna("Offbooks")

    segments = sorted(working["SEGMENT"].dropna().unique(), key=str)
    monthly_matrices: dict[str, dict[str, dict[str, list[float]]]] = {}
    aggregate_matrices: dict[str, dict[str, list[float]]] = {}
    proportion_matrices: dict[str, dict[str, list[float]]] = {}
    normalized_matrices: dict[str, dict[str, list[float]]] = {}
    cure_rates: dict[str, float] = {}

    rows: list[dict[str, Any]] = []

    for segment in segments:
        segment_df = working[working["SEGMENT"] == segment]
        reporting_months = sorted(segment_df["Reporting Month"].unique())

        monthly_matrices[segment] = {}
        aggregate = np.zeros((3, 3), dtype=np.float64)

        for reporting_month in reporting_months:
            month_df = segment_df[segment_df["Reporting Month"] == reporting_month]
            month_matrix = _build_monthly_matrix(month_df)
            aggregate += month_matrix
            month_key = pd.Timestamp(reporting_month).strftime("%Y-%m-%d")
            monthly_matrices[segment][month_key] = _matrix_to_dict(month_matrix)

        aggregate_matrices[segment] = _matrix_to_dict(aggregate)

        # Steps 5–7 — row proportions, cure rate, normalize.
        proportions = _row_proportions(aggregate)
        proportion_matrices[segment] = _matrix_to_dict(proportions)
        cure_rates[segment] = float(proportions[2, 0] + proportions[2, 1])
        normalized = _normalize_matrix(proportions)
        normalized_matrices[segment] = _matrix_to_dict(normalized)

        # Steps 8–9 — matrix powers and long-form table.
        for month in range(1, MAX_PD_MONTH + 1):
            powered = matrix_power(normalized, month)
            for transition_idx, transition in enumerate(STAGES):
                rows.append(
                    {
                        "SEGMENT": segment,
                        "Month": month,
                        "Transition": transition,
                        "Stage_1_prob": float(powered[transition_idx, 0]),
                        "Stage_2_prob": float(powered[transition_idx, 1]),
                        "Stage_3_prob": float(powered[transition_idx, 2]),
                    }
                )

    output = pd.DataFrame(rows)
    if output.empty:
        output = pd.DataFrame(
            columns=[
                "SEGMENT",
                "Month",
                "Transition",
                "Stage_1_prob",
                "Stage_2_prob",
                "Stage_3_prob",
                "Marginal_PD",
                "Cure_Rate",
            ]
        )
    else:
        output = output.sort_values(
            ["SEGMENT", "Transition", "Month"],
            kind="mergesort",
        ).reset_index(drop=True)

        # Step 10 — marginal PD.
        output["Marginal_PD"] = (
            output.groupby(["SEGMENT", "Transition"], sort=False, group_keys=False)
            .apply(_compute_marginal_pd)
            .to_numpy(dtype=np.float64)
        )

        # Step 11 — cure rate column.
        output["Cure_Rate"] = output["SEGMENT"].map(cure_rates).astype(np.float64)

    intermediates: dict[str, Any] = {
        "monthly_matrices": monthly_matrices,
        "aggregate": aggregate_matrices,
        "proportion": proportion_matrices,
        "normalized": normalized_matrices,
    }

    return output, cure_rates, intermediates
