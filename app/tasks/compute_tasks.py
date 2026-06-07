"""Celery compute pipeline: PD, LGD, and EAD/ECL tasks."""

from __future__ import annotations

import asyncio
import gc
import io
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pandas as pd
from celery import chord, group
from sqlalchemy import select, text, update

from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

_log = get_logger(__name__)

STAGE_KEYS = ("pd", "lgd", "ead", "ecl")


def _run(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine from a synchronous Celery task."""
    return asyncio.run(coro)


def _initial_engine_progress() -> dict[str, dict[str, Any]]:
    return {
        stage: {
            "status": "pending",
            "started_at": None,
            "finished_at": None,
            "elapsed_ms": None,
        }
        for stage in STAGE_KEYS
    }


def _merge_progress(
    current: dict[str, Any] | None,
    stage: str,
    *,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    elapsed_ms: int | None = None,
) -> dict[str, Any]:
    progress = dict(current or _initial_engine_progress())
    stage_data = dict(progress.get(stage, _initial_engine_progress()[stage]))
    stage_data["status"] = status
    if started_at is not None:
        stage_data["started_at"] = started_at
    if finished_at is not None:
        stage_data["finished_at"] = finished_at
    if elapsed_ms is not None:
        stage_data["elapsed_ms"] = elapsed_ms
    progress[stage] = stage_data
    return progress


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


async def _load_run(db, run_id: str):
    from app.modules.runs.models import Run

    result = await db.execute(select(Run).where(Run.id == run_id, Run.deleted_at.is_(None)))
    run = result.scalar_one_or_none()
    if run is None:
        msg = f"Run {run_id} not found"
        raise ValueError(msg)
    return run


async def _get_engine_progress(db, run_id: str) -> dict[str, Any]:
    from app.modules.runs.models import Run

    result = await db.execute(select(Run.engine_progress).where(Run.id == run_id))
    current = result.scalar_one_or_none()
    if not current:
        return _initial_engine_progress()
    merged = _initial_engine_progress()
    merged.update(current)
    for stage in STAGE_KEYS:
        merged[stage] = {**_initial_engine_progress()[stage], **merged.get(stage, {})}
    return merged


async def _save_engine_progress(db, run_id: str, progress: dict[str, Any], **extra_values: Any) -> None:
    from app.modules.runs.models import Run

    values = {"engine_progress": progress, **extra_values}
    await db.execute(update(Run).where(Run.id == run_id).values(**values))
    await db.commit()


async def _mark_stage_running(db, run_id: str, stage: str, run_status: str) -> str:
    started_at = _iso_now()
    progress = _merge_progress(await _get_engine_progress(db, run_id), stage, status="running", started_at=started_at)
    await _save_engine_progress(db, run_id, progress, status=run_status)
    return started_at


async def _mark_stage_complete(db, run_id: str, stage: str, started_at: str) -> dict[str, Any]:
    finished_at = _iso_now()
    elapsed_ms = int((datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
    progress = _merge_progress(
        await _get_engine_progress(db, run_id),
        stage,
        status="complete",
        finished_at=finished_at,
        elapsed_ms=elapsed_ms,
    )
    await _save_engine_progress(db, run_id, progress)
    return progress


async def _mark_run_failed(db, run_id: str, stage: str, exc: Exception) -> None:
    failure_ref = str(uuid4())
    progress = _merge_progress(await _get_engine_progress(db, run_id), stage, status="error")
    await _save_engine_progress(
        db,
        run_id,
        progress,
        status="failed",
        failure_stage=stage,
        failure_message=str(exc),
        failure_ref=failure_ref,
        finished_at=datetime.now(UTC),
    )


async def _load_uploads(db, run_id: str, kind: str):
    from app.modules.runs.models import Upload

    result = await db.execute(
        select(Upload)
        .where(Upload.run_id == run_id, Upload.kind == kind)
        .order_by(Upload.created_at.asc())
    )
    return list(result.scalars().all())


async def _download_uploads(uploads) -> list[bytes]:
    from app.core.storage import download_bytes

    return [await download_bytes(upload.storage_path) for upload in uploads]


def _combine_excel_bytes(files: list[bytes]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for data in files:
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
        for sheet_df in sheets.values():
            if not sheet_df.empty:
                frames.append(sheet_df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


async def _input_hashes(db, run_id: str) -> str:
    from app.modules.runs.models import Upload

    result = await db.execute(
        select(Upload.sha256).where(Upload.run_id == run_id).order_by(Upload.kind.asc(), Upload.created_at.asc())
    )
    return ",".join(result.scalars().all())


async def _load_collateral_config(db, tenant_id: str) -> list[dict[str, Any]]:
    from app.modules.collateral.models import CollateralType

    result = await db.execute(
        select(CollateralType).where(
            CollateralType.tenant_id == tenant_id,
            CollateralType.deleted_at.is_(None),
        )
    )
    return [
        {
            "name": row.name,
            "haircut": float(row.haircut) / 100.0,
            "time_to_realize": row.time_to_realize,
        }
        for row in result.scalars().all()
    ]


async def _load_pd_dataframe(db, run_id: str) -> pd.DataFrame:
    from app.modules.results.models import PdResult

    result = await db.execute(select(PdResult).where(PdResult.run_id == run_id))
    rows = result.scalars().all()
    if not rows:
        return pd.DataFrame(
            columns=[
                "SEGMENT",
                "Month",
                "Transition",
                "Marginal_PD",
                "Cure_Rate",
                "Stage_1_prob",
                "Stage_2_prob",
                "Stage_3_prob",
            ]
        )
    return pd.DataFrame(
        [
            {
                "SEGMENT": row.segment,
                "Month": row.month,
                "Transition": row.transition,
                "Marginal_PD": float(row.marginal_pd),
                "Cure_Rate": float(row.cure_rate),
                "Stage_1_prob": float(row.s1_prob),
                "Stage_2_prob": float(row.s2_prob),
                "Stage_3_prob": float(row.s3_prob),
            }
            for row in rows
        ]
    )


async def _load_lgd_dataframe(db, run_id: str) -> pd.DataFrame:
    from app.modules.results.models import LgdResult

    result = await db.execute(select(LgdResult).where(LgdResult.run_id == run_id))
    rows = result.scalars().all()
    if not rows:
        return pd.DataFrame(columns=["Loan ID", "Customer ID", "EIR", "Sum of Discounted Collaterals per Loan ID"])
    return pd.DataFrame(
        [
            {
                "Loan ID": row.loan_id,
                "Customer ID": row.customer_id,
                "EIR": float(row.eir),
                "Sum of Discounted Collaterals per Loan ID": row.sum_discounted_collat,
            }
            for row in rows
        ]
    )


async def _compute_run_totals(conn, run_id: str) -> tuple[Decimal, Decimal, Decimal]:
    total_ecl_result = await conn.execute(
        text(
            """
            SELECT COALESCE(SUM(discounted_ecl), 0) AS total_ecl
            FROM ead_results
            WHERE run_id = :run_id
            """
        ),
        {"run_id": run_id},
    )
    total_ecl = Decimal(str(total_ecl_result.scalar_one()))

    outstanding_result = await conn.execute(
        text(
            """
            SELECT COALESCE(SUM(max_bal), 0) AS total_outstanding
            FROM (
                SELECT MAX(bal_after_missed) AS max_bal
                FROM ead_results
                WHERE run_id = :run_id
                GROUP BY loan_id
            ) loan_balances
            """
        ),
        {"run_id": run_id},
    )
    total_outstanding = Decimal(str(outstanding_result.scalar_one()))
    coverage = (total_ecl / total_outstanding) if total_outstanding > 0 else Decimal("0")
    return total_ecl, total_outstanding, coverage


async def _upload_workbooks(
    db,
    run,
    workbooks: dict[str, bytes],
    artifact_kinds: dict[str, str],
) -> None:
    from app.core.security import new_ulid
    from app.core.storage import build_storage_path, upload_stream
    from app.modules.results.models import OutputArtifact

    for filename, content in workbooks.items():
        storage_path = build_storage_path(run.tenant_id, run.id, "outputs", filename)
        sha256, file_size = await upload_stream(
            storage_path,
            io.BytesIO(content),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        db.add(
            OutputArtifact(
                id=new_ulid(),
                run_id=run.id,
                tenant_id=run.tenant_id,
                kind=artifact_kinds[filename],
                storage_path=storage_path,
                sha256=sha256,
                file_size_bytes=file_size,
            )
        )
    await db.commit()


@celery_app.task(name="pd_task", bind=True)
def pd_task(self, run_id: str) -> dict[str, str]:  # type: ignore[misc]
    async def _compute() -> dict[str, str]:
        from app.core.run_enums import RunStatus, UploadKind
        from app.database import AsyncSessionLocal, engine
        from app.engine.bulk_insert import bulk_insert_pd_results
        from app.engine.pd_engine import compute_pd

        async with AsyncSessionLocal() as db:
            run = await _load_run(db, run_id)
            started_at = await _mark_stage_running(db, run.id, "pd", RunStatus.PD_RUNNING.value)
            _log.info("compute_stage_started", run_id=run_id, stage="pd")

            try:
                uploads = await _load_uploads(db, run_id, UploadKind.PD.value)
                if not uploads:
                    msg = "No PD uploads found for run"
                    raise ValueError(msg)

                files = await _download_uploads(uploads)
                if not run.combine_pd_files and len(files) > 1:
                    files = files[:1]

                pd_input = _combine_excel_bytes(files)
                pd_output, _cure_rates, _intermediates = compute_pd(pd_input)

                async with engine.begin() as conn:
                    await bulk_insert_pd_results(conn, run.id, run.tenant_id, pd_output)

                progress = await _mark_stage_complete(db, run.id, "pd", started_at)
                _log.info(
                    "compute_stage_completed",
                    run_id=run_id,
                    stage="pd",
                    elapsed_ms=progress.get("pd", {}).get("elapsed_ms"),
                )
                return {"run_id": run_id, "stage": "pd"}
            except Exception as exc:
                _log.error("compute_stage_failed", run_id=run_id, stage="pd", exc_info=exc)
                await _mark_run_failed(db, run.id, "pd", exc)
                raise

    return _run(_compute())


@celery_app.task(name="lgd_task", bind=True)
def lgd_task(self, run_id: str) -> dict[str, str]:  # type: ignore[misc]
    async def _compute() -> dict[str, str]:
        from app.core.run_enums import RunStatus, UploadKind
        from app.database import AsyncSessionLocal, engine
        from app.engine.bulk_insert import bulk_insert_lgd_results
        from app.engine.lgd_engine import compute_lgd

        async with AsyncSessionLocal() as db:
            run = await _load_run(db, run_id)
            started_at = await _mark_stage_running(db, run.id, "lgd", RunStatus.LGD_RUNNING.value)
            _log.info("compute_stage_started", run_id=run_id, stage="lgd")

            try:
                uploads = await _load_uploads(db, run_id, UploadKind.LGD.value)
                if not uploads:
                    msg = "No LGD uploads found for run"
                    raise ValueError(msg)

                files = await _download_uploads(uploads)
                lgd_input = _combine_excel_bytes(files)
                collateral_config = await _load_collateral_config(db, run.tenant_id)
                lgd_output = compute_lgd(lgd_input, collateral_config)

                async with engine.begin() as conn:
                    await bulk_insert_lgd_results(conn, run.id, run.tenant_id, lgd_output)

                progress = await _mark_stage_complete(db, run.id, "lgd", started_at)
                _log.info(
                    "compute_stage_completed",
                    run_id=run_id,
                    stage="lgd",
                    elapsed_ms=progress.get("lgd", {}).get("elapsed_ms"),
                )
                return {"run_id": run_id, "stage": "lgd"}
            except Exception as exc:
                _log.error("compute_stage_failed", run_id=run_id, stage="lgd", exc_info=exc)
                await _mark_run_failed(db, run.id, "lgd", exc)
                raise

    return _run(_compute())


@celery_app.task(name="ead_ecl_task", bind=True)
def ead_ecl_task(self, _group_results: list[Any], run_id: str) -> dict[str, str]:  # type: ignore[misc]
    async def _compute() -> dict[str, str]:
        from app.core.run_enums import OutputArtifactKind, RunStatus, UploadKind
        from app.database import AsyncSessionLocal, engine
        from app.engine import ENGINE_VERSION
        from app.engine.bulk_insert import bulk_insert_ead_results
        from app.engine.ead_engine import compute_ead
        from app.engine.excel_writer import build_ecl_aggregates, generate_all_workbooks
        from app.engine.lgd_engine import compute_lgd
        from app.engine.pd_engine import compute_pd

        async with AsyncSessionLocal() as db:
            run = await _load_run(db, run_id)
            started_at = await _mark_stage_running(db, run.id, "ead", RunStatus.EAD_RUNNING.value)
            _log.info("compute_stage_started", run_id=run_id, stage="ead")

            ead_df = pd.DataFrame()
            run_warnings: list[str] = []
            active_stage = "ead"

            try:
                ead_uploads = await _load_uploads(db, run_id, UploadKind.EAD.value)
                if not ead_uploads:
                    msg = "No EAD uploads found for run"
                    raise ValueError(msg)

                ead_files = await _download_uploads(ead_uploads)
                ead_input = _combine_excel_bytes(ead_files)

                pd_df = await _load_pd_dataframe(db, run_id)
                lgd_df = await _load_lgd_dataframe(db, run_id)
                ead_df, run_warnings = compute_ead(ead_input, pd_df, lgd_df)

                async with engine.begin() as conn:
                    await bulk_insert_ead_results(conn, run.id, run.tenant_id, ead_df)

                del pd_df, lgd_df
                gc.collect()

                ecl_started_at = _iso_now()
                active_stage = "ecl"
                progress = _merge_progress(
                    await _get_engine_progress(db, run.id),
                    "ecl",
                    status="running",
                    started_at=ecl_started_at,
                )
                await _save_engine_progress(db, run.id, progress)

                aggregates = build_ecl_aggregates(ead_df, ead_input)
                total_ecl = Decimal(str(aggregates["total_ecl"]))
                total_outstanding = Decimal(str(aggregates["total_outstanding"]))
                coverage_ratio = Decimal(str(aggregates["coverage_ratio"]))

                async with engine.begin() as conn:
                    sql_total_ecl, sql_outstanding, sql_coverage = await _compute_run_totals(conn, run_id)
                    total_ecl = sql_total_ecl
                    total_outstanding = sql_outstanding
                    coverage_ratio = sql_coverage

                pd_uploads = await _load_uploads(db, run_id, UploadKind.PD.value)
                pd_files = await _download_uploads(pd_uploads)
                if not run.combine_pd_files and len(pd_files) > 1:
                    pd_files = pd_files[:1]
                pd_input = _combine_excel_bytes(pd_files)
                pd_output, cure_rates, intermediates = compute_pd(pd_input)

                lgd_uploads = await _load_uploads(db, run_id, UploadKind.LGD.value)
                lgd_files = await _download_uploads(lgd_uploads)
                lgd_input = _combine_excel_bytes(lgd_files)
                collateral_config = await _load_collateral_config(db, run.tenant_id)
                lgd_full_df = compute_lgd(lgd_input, collateral_config)

                timestamp_utc = _iso_now()
                input_hashes = await _input_hashes(db, run_id)
                run_meta = {
                    "run_id": run.id,
                    "tenant_id": run.tenant_id,
                    "timestamp_utc": timestamp_utc,
                    "engine_version": run.engine_version or ENGINE_VERSION,
                    "input_hashes": input_hashes,
                }
                pd_data = {
                    "pd_df": pd_output,
                    "cure_rates": cure_rates,
                    "intermediates": intermediates,
                }
                aggregates["ecl_total"]["Run ID"] = run.id
                aggregates["ecl_total"]["Engine Version"] = run_meta["engine_version"]
                aggregates["ecl_total"]["Timestamp UTC"] = timestamp_utc
                aggregates["total_ecl"] = float(total_ecl)
                aggregates["total_outstanding"] = float(total_outstanding)
                aggregates["coverage_ratio"] = float(coverage_ratio)

                workbooks = generate_all_workbooks(
                    run_meta,
                    pd_data,
                    lgd_full_df,
                    ead_df,
                    aggregates,
                )
                artifact_kinds = {
                    "PD Calcs.xlsx": OutputArtifactKind.PD_CALCS.value,
                    "LGD.xlsx": OutputArtifactKind.LGD.value,
                    "Contractual Rundown.xlsx": OutputArtifactKind.RUNDOWN.value,
                    "ECL Summary.xlsx": OutputArtifactKind.ECL_SUMMARY.value,
                }
                await _upload_workbooks(db, run, workbooks, artifact_kinds)

                del pd_input, pd_output, lgd_input, lgd_full_df, ead_input, workbooks
                gc.collect()

                ead_progress = await _mark_stage_complete(db, run.id, "ead", started_at)
                _log.info(
                    "compute_stage_completed",
                    run_id=run_id,
                    stage="ead",
                    elapsed_ms=ead_progress.get("ead", {}).get("elapsed_ms"),
                )
                ecl_finished_at = _iso_now()
                ecl_elapsed_ms = int(
                    (datetime.fromisoformat(ecl_finished_at) - datetime.fromisoformat(ecl_started_at)).total_seconds()
                    * 1000
                )
                progress = _merge_progress(
                    await _get_engine_progress(db, run.id),
                    "ecl",
                    status="complete",
                    finished_at=ecl_finished_at,
                    elapsed_ms=ecl_elapsed_ms,
                )
                await _save_engine_progress(
                    db,
                    run.id,
                    progress,
                    status=RunStatus.COMPLETE.value,
                    total_ecl=total_ecl,
                    total_outstanding=total_outstanding,
                    coverage_ratio=coverage_ratio,
                    run_warnings=run_warnings or None,
                    finished_at=datetime.now(UTC),
                )
                _log.info("compute_stage_completed", run_id=run_id, stage="ecl", elapsed_ms=ecl_elapsed_ms)
                return {"run_id": run_id, "stage": "ead_ecl"}
            except Exception as exc:
                _log.error("compute_stage_failed", run_id=run_id, stage=active_stage, exc_info=exc)
                await _mark_run_failed(db, run.id, active_stage, exc)
                raise

    return _run(_compute())


@celery_app.task(name="enqueue_compute_pipeline")
def enqueue_compute_pipeline(run_id: str) -> None:
    """Enqueue the PD/LGD parallel chord followed by EAD/ECL."""
    header = group(pd_task.s(run_id), lgd_task.s(run_id))
    callback = ead_ecl_task.s(run_id)
    chord(header)(callback)
