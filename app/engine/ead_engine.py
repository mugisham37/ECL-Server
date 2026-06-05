"""EAD (Exposure at Default) and ECL computation engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import numpy_financial as npf
import pandas as pd

_STAGING_ALIASES = ("Staging", "Staging (Stage)")
_EIR_ALIASES = ("Effective Interest Rate", "Effective Interest Rate (EIR)", "EIR")
_LGD_SUM_COL = "Sum of Discounted Collaterals per Loan ID"
_LGD_SUM_SHORT = "Sum of Discounted Collaterals"
_MISSED_EPS = 1e-9


def _resolve_column(df: pd.DataFrame, names: tuple[str, ...], default: str) -> str:
    for name in names:
        if name in df.columns:
            return name
    return default


def _to_decimal(value: float | int | Decimal) -> Decimal:
    return Decimal(str(value))


def _months_between(start: date | pd.Timestamp, end: date | pd.Timestamp) -> int:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return (end_ts.year - start_ts.year) * 12 + (end_ts.month - start_ts.month)


def _monthly_instalment(outstanding: float, eir: float, remaining_term: int) -> float:
    if remaining_term <= 0:
        return 0.0
    monthly_rate = eir / 12.0
    if monthly_rate == 0.0:
        return outstanding / remaining_term
    return float(-npf.pmt(monthly_rate, remaining_term, outstanding))


def _generate_snapshot_dates(
    reporting_date: pd.Timestamp,
    maturity_date: pd.Timestamp,
    staging: str,
) -> list[pd.Timestamp]:
    if staging == "Stage 3":
        return [reporting_date]

    if staging == "Stage 1":
        offsets = range(13)
    else:
        max_months = max(0, _months_between(reporting_date, maturity_date))
        offsets = range(max_months + 1)

    dates: list[pd.Timestamp] = []
    for offset in offsets:
        snapshot = reporting_date + pd.DateOffset(months=offset)
        if snapshot > maturity_date:
            break
        dates.append(snapshot)
    return dates or [reporting_date]


def _count_missed_periods(
    row_idx: int,
    opening_balances: list[float],
    monthly_rate: float,
    monthly_instalment: float,
) -> int:
    missed = 0
    for prior_idx in range(max(0, row_idx - 3), row_idx):
        opening = opening_balances[prior_idx]
        if monthly_instalment <= 0:
            continue
        balance_after_interest = opening * (1.0 + monthly_rate)
        if balance_after_interest + _MISSED_EPS < monthly_instalment:
            missed += 1
    return min(missed, 3)


def _walk_loan_balances(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("Snapshot Date", kind="mergesort").copy()
    outstanding = float(group["Outstanding Amount"].iloc[0])
    eir = float(group["EIR"].iloc[0])
    monthly_rate = eir / 12.0
    instalment = float(group["Monthly Instalment"].iloc[0])

    balances_after_repayment: list[float] = []
    balances_after_missed: list[float] = []
    opening_balances: list[float] = []

    for row_idx in range(len(group)):
        if row_idx == 0:
            opening = outstanding
        else:
            opening = balances_after_repayment[row_idx - 1]

        opening_balances.append(opening)
        after_repayment = opening * (1.0 + monthly_rate) - instalment
        if after_repayment < 0:
            after_repayment = 0.0
        balances_after_repayment.append(after_repayment)

        missed_count = _count_missed_periods(row_idx, opening_balances, monthly_rate, instalment)
        after_missed = after_repayment * ((1.0 + monthly_rate) ** missed_count)
        balances_after_missed.append(after_missed)

    group["Balance After Repayment"] = balances_after_repayment
    group["Balance After Missed Payment"] = balances_after_missed
    group["Period to be Discounted"] = range(len(group))
    return group


def compute_ead(
    ead_df: pd.DataFrame,
    pd_df: pd.DataFrame,
    lgd_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Run the EAD/ECL computation pipeline."""
    warnings: list[str] = []
    working = ead_df.copy()

    staging_col = _resolve_column(working, _STAGING_ALIASES, "Staging")
    if staging_col != "Staging":
        working = working.rename(columns={staging_col: "Staging"})

    eir_col = _resolve_column(working, _EIR_ALIASES, "Effective Interest Rate")
    if eir_col != "Effective Interest Rate":
        working = working.rename(columns={eir_col: "Effective Interest Rate"})

    working = working.sort_values(["Loan ID"], kind="mergesort").reset_index(drop=True)

    lgd_subset = lgd_df[["Loan ID"]].copy()
    if "EIR" in lgd_df.columns:
        lgd_subset["EIR"] = lgd_df["EIR"]
    if _LGD_SUM_COL in lgd_df.columns:
        lgd_subset[_LGD_SUM_SHORT] = lgd_df[_LGD_SUM_COL]
    elif _LGD_SUM_SHORT in lgd_df.columns:
        lgd_subset[_LGD_SUM_SHORT] = lgd_df[_LGD_SUM_SHORT]
    else:
        lgd_subset[_LGD_SUM_SHORT] = 0.0
    lgd_subset = lgd_subset.drop_duplicates(subset=["Loan ID"], keep="first")

    merged = working.merge(lgd_subset, on="Loan ID", how="left")

    missing_lgd_mask = merged[_LGD_SUM_SHORT].isna()
    for loan_id in sorted(merged.loc[missing_lgd_mask, "Loan ID"].astype(str).unique()):
        warnings.append(
            f"EC-06: Loan {loan_id} in EAD but not in LGD — collateral treated as 0"
        )
    merged[_LGD_SUM_SHORT] = merged[_LGD_SUM_SHORT].fillna(0.0)

    if "EIR" in merged.columns:
        merged["EIR"] = merged["EIR"].fillna(merged["Effective Interest Rate"])
    else:
        merged["EIR"] = merged["Effective Interest Rate"]

    # Step 2 — generate snapshot rows.
    snapshot_rows: list[dict[str, Any]] = []
    for _, loan in merged.iterrows():
        reporting_date = pd.Timestamp(loan["Reporting Date"])
        maturity_date = pd.Timestamp(loan["Maturity Date"])
        snapshot_dates = _generate_snapshot_dates(
            reporting_date,
            maturity_date,
            str(loan["Staging"]),
        )
        for snapshot_date in snapshot_dates:
            row = loan.to_dict()
            row["Snapshot Date"] = snapshot_date
            snapshot_rows.append(row)

    if not snapshot_rows:
        empty = pd.DataFrame(
            columns=[
                "Loan ID",
                "Customer ID",
                "SEGMENT",
                "Staging",
                "Snapshot Date",
                "Period Since Origination",
                "Monthly Instalment",
                "Balance After Repayment",
                "Balance After Missed Payment",
                "Period to be Discounted",
                "Marginal PD",
                "Cure Rate",
                "LGW",
                "LGD",
                "Credit Loss",
                "Discounted ECL",
            ]
        )
        return empty, warnings

    snapshots = pd.DataFrame(snapshot_rows)
    snapshots["Reporting Date"] = pd.to_datetime(snapshots["Reporting Date"])
    snapshots["First Payment Date"] = pd.to_datetime(snapshots["First Payment Date"])
    snapshots["Adjusted Maturity Date"] = pd.to_datetime(snapshots["Adjusted Maturity Date"])
    snapshots["Snapshot Date"] = pd.to_datetime(snapshots["Snapshot Date"])

    # Step 3 — period since origination.
    snapshots["Period Since Origination"] = [
        _months_between(first_payment, snapshot)
        for first_payment, snapshot in zip(
            snapshots["First Payment Date"],
            snapshots["Snapshot Date"],
            strict=True,
        )
    ]

    # Step 4 — monthly instalment (once per loan).
    loan_terms = snapshots.drop_duplicates(subset=["Loan ID"], keep="first").copy()
    instalments: dict[str, float] = {}
    for _, loan in loan_terms.iterrows():
        elapsed = _months_between(loan["First Payment Date"], loan["Reporting Date"])
        total_term = _months_between(loan["First Payment Date"], loan["Adjusted Maturity Date"])
        remaining = total_term - elapsed
        instalments[str(loan["Loan ID"])] = _monthly_instalment(
            float(loan["Outstanding Amount"]),
            float(loan["EIR"]),
            remaining,
        )
    snapshots["Monthly Instalment"] = snapshots["Loan ID"].astype(str).map(instalments)

    # Steps 5–7 — balances and discount period via sequential group walk.
    snapshots = (
        snapshots.groupby("Loan ID", sort=True, group_keys=False)
        .apply(_walk_loan_balances)
        .reset_index(drop=True)
    )

    # Step 8 — join PD results.
    pd_lookup = pd_df[
        [
            "SEGMENT",
            "Month",
            "Transition",
            "Marginal_PD",
            "Cure_Rate",
        ]
    ].copy()
    pd_lookup = pd_lookup.rename(
        columns={
            "Month": "Period Since Origination",
            "Transition": "Staging",
        }
    )

    snapshots = snapshots.merge(
        pd_lookup,
        on=["SEGMENT", "Period Since Origination", "Staging"],
        how="left",
    )

    # Steps 9–11 — LGW, LGD, credit loss, discounted ECL.
    bal_after_missed = snapshots["Balance After Missed Payment"].astype(float)
    collateral = snapshots[_LGD_SUM_SHORT].astype(float)

    lgw = np.where(
        bal_after_missed <= 0,
        0.0,
        np.maximum(1.0 - collateral / bal_after_missed, 0.0),
    )
    snapshots["LGW"] = lgw

    cure_rate = snapshots["Cure_Rate"].fillna(0.0).astype(float)
    snapshots["LGD"] = snapshots["LGW"] * (1.0 - cure_rate)

    marginal_pd = snapshots["Marginal_PD"].fillna(0.0).astype(float)
    snapshots["Credit Loss"] = bal_after_missed * marginal_pd * snapshots["LGD"].astype(float)

    monthly_rate = snapshots["EIR"].astype(float) / 12.0
    period_to_discount = snapshots["Period to be Discounted"].astype(int)
    discount_factor = np.where(
        period_to_discount > 0,
        (1.0 + monthly_rate) ** (-period_to_discount),
        1.0,
    )
    snapshots["Discounted ECL"] = snapshots["Credit Loss"] * discount_factor

    decimal_cols = [
        "Monthly Instalment",
        "Balance After Repayment",
        "Balance After Missed Payment",
        "Credit Loss",
        "Discounted ECL",
        _LGD_SUM_SHORT,
    ]
    for col in decimal_cols:
        if col in snapshots.columns:
            snapshots[col] = snapshots[col].apply(_to_decimal)

    output_cols = [
        "Loan ID",
        "Customer ID",
        "SEGMENT",
        "Staging",
        "Snapshot Date",
        "Period Since Origination",
        "Period to be Discounted",
        "Monthly Instalment",
        "Balance After Repayment",
        "Balance After Missed Payment",
        _LGD_SUM_SHORT,
        "Marginal PD",
        "Cure Rate",
        "LGW",
        "LGD",
        "Credit Loss",
        "Discounted ECL",
    ]
    output = snapshots[output_cols].sort_values(
        ["Loan ID", "Snapshot Date"],
        kind="mergesort",
    ).reset_index(drop=True)

    return output, warnings
