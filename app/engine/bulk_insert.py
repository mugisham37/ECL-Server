"""Bulk insert helpers for compute result tables."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.security import new_ulid

BATCH_SIZE = 5000

_INSERT_PD = """
INSERT INTO pd_results (
    id, run_id, tenant_id, segment, month, transition,
    s1_prob, s2_prob, s3_prob, marginal_pd, cure_rate
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
"""

_INSERT_LGD = """
INSERT INTO lgd_results (
    id, run_id, tenant_id, loan_id, customer_id, eir, sum_discounted_collat
) VALUES ($1, $2, $3, $4, $5, $6, $7)
"""

_INSERT_EAD = """
INSERT INTO ead_results (
    id, run_id, tenant_id, loan_id, customer_id, segment, stage,
    snapshot_date, period_since_orig, period_to_discount,
    monthly_instalment, bal_after_repayment, bal_after_missed,
    marginal_pd, lgw, lgd, credit_loss, discounted_ecl
) VALUES (
    $1, $2, $3, $4, $5, $6, $7,
    $8, $9, $10,
    $11, $12, $13,
    $14, $15, $16, $17, $18
)
"""

_LGD_SUM_COL = "Sum of Discounted Collaterals per Loan ID"


def _chunks(records: list[tuple[Any, ...]], size: int) -> list[list[tuple[Any, ...]]]:
    return [records[i : i + size] for i in range(0, len(records), size)]


async def _executemany(conn: AsyncConnection, query: str, records: list[tuple[Any, ...]]) -> int:
    if not records:
        return 0

    raw = await conn.get_raw_connection()
    pg_conn = raw.driver_connection
    inserted = 0
    for batch in _chunks(records, BATCH_SIZE):
        await pg_conn.executemany(query, batch)
        inserted += len(batch)
    return inserted


def _to_decimal(value: Any) -> Decimal:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return Decimal("0")
    return Decimal(str(value))


def _to_date(value: Any) -> date:
    return pd.Timestamp(value).date()


def _pd_records(run_id: str, tenant_id: str, df: pd.DataFrame) -> list[tuple[Any, ...]]:
    return [
        (
            new_ulid(),
            run_id,
            tenant_id,
            str(row["SEGMENT"]),
            int(row["Month"]),
            str(row["Transition"]),
            float(row["Stage_1_prob"]),
            float(row["Stage_2_prob"]),
            float(row["Stage_3_prob"]),
            float(row["Marginal_PD"]),
            float(row["Cure_Rate"]),
        )
        for row in df.to_dict(orient="records")
    ]


def _lgd_records(run_id: str, tenant_id: str, df: pd.DataFrame) -> list[tuple[Any, ...]]:
    return [
        (
            new_ulid(),
            run_id,
            tenant_id,
            str(row["Loan ID"]),
            str(row["Customer ID"]),
            _to_decimal(row["EIR"]),
            _to_decimal(row[_LGD_SUM_COL]),
        )
        for row in df.to_dict(orient="records")
    ]


def _ead_records(run_id: str, tenant_id: str, df: pd.DataFrame) -> list[tuple[Any, ...]]:
    records: list[tuple[Any, ...]] = []
    for row in df.to_dict(orient="records"):
        marginal_pd = row.get("Marginal PD")
        records.append(
            (
                new_ulid(),
                run_id,
                tenant_id,
                str(row["Loan ID"]),
                str(row["Customer ID"]),
                str(row["SEGMENT"]),
                str(row["Staging"]),
                _to_date(row["Snapshot Date"]),
                int(row["Period Since Origination"]),
                int(row["Period to be Discounted"]),
                _to_decimal(row["Monthly Instalment"]),
                _to_decimal(row["Balance After Repayment"]),
                _to_decimal(row["Balance After Missed Payment"]),
                None if marginal_pd is None or pd.isna(marginal_pd) else _to_decimal(marginal_pd),
                _to_decimal(row["LGW"]),
                _to_decimal(row["LGD"]),
                _to_decimal(row["Credit Loss"]),
                _to_decimal(row["Discounted ECL"]),
            )
        )
    return records


async def bulk_insert_pd_results(
    conn: AsyncConnection,
    run_id: str,
    tenant_id: str,
    df: pd.DataFrame,
) -> int:
    """Insert PD result rows in batches of 5,000."""
    return await _executemany(conn, _INSERT_PD, _pd_records(run_id, tenant_id, df))


async def bulk_insert_lgd_results(
    conn: AsyncConnection,
    run_id: str,
    tenant_id: str,
    df: pd.DataFrame,
) -> int:
    """Insert LGD result rows in batches of 5,000."""
    return await _executemany(conn, _INSERT_LGD, _lgd_records(run_id, tenant_id, df))


async def bulk_insert_ead_results(
    conn: AsyncConnection,
    run_id: str,
    tenant_id: str,
    df: pd.DataFrame,
) -> int:
    """Insert EAD result rows in batches of 5,000."""
    return await _executemany(conn, _INSERT_EAD, _ead_records(run_id, tenant_id, df))
