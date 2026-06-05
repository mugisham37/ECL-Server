"""Runs service — create, upload, validate, execute, list, detail, delete."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.exceptions import ECLException
from app.core.pagination import PageMeta
from app.core.run_enums import RunStatus, UploadKind, ValidationStatus
from app.core.security import new_ulid
from app.core.storage import build_storage_path, delete_object, download_bytes, upload_stream
from app.engine import (
    EAD_METHOD,
    ENGINE_RELEASED_DATE,
    ENGINE_VERSION,
    LGD_METHOD,
    PD_METHOD,
)
from app.engine.format_utils import (
    format_amount,
    format_compact_amount,
    format_coverage,
    format_file_size,
    map_run_status_to_api,
    short_ulid,
)
from app.engine.validators import validate_ead, validate_lgd, validate_pd
from app.engine.validators.base import ValidationIssue
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import log_event
from app.modules.auth.models import User
from app.modules.auth.utils import user_initials
from app.modules.collateral.models import CollateralType
from app.modules.runs.models import Run, Upload
from app.modules.tenants.models import TenantMembership


def get_run_scope_filter(
    user: User,
    tenant_id: str,
    membership: TenantMembership | None,
):
    """Returns a SQLAlchemy WHERE clause fragment that scopes run visibility."""
    if user.is_platform_admin:
        return Run.tenant_id == tenant_id

    if membership is None:
        raise ECLException("NO_MEMBERSHIP", "User has no membership in this tenant.", 403)

    if membership.role == UserRole.ADMINISTRATOR.value:
        return Run.tenant_id == tenant_id

    return and_(Run.tenant_id == tenant_id, Run.created_by_user_id == user.id)


async def assert_run_visible(
    db: AsyncSession,
    user: User,
    tenant_id: str,
    membership: TenantMembership | None,
    run_id: str,
) -> Run:
    result = await db.execute(
        select(Run).where(Run.id == run_id, Run.tenant_id == tenant_id, Run.deleted_at.is_(None))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise ECLException("RUN_NOT_FOUND", "Run not found.", 404)

    if not user.is_platform_admin:
        if membership is None:
            raise ECLException("RUN_NOT_FOUND", "Run not found.", 404)
        if membership.role in (UserRole.ANALYST.value, UserRole.REVIEWER.value):
            if run.created_by_user_id != user.id:
                raise ECLException("RUN_NOT_FOUND", "Run not found.", 404)

    return run
from app.modules.runs.schemas import (
    CreateRunRequest,
    EngineInfoOut,
    EngineProgressOut,
    EngineStageProgressOut,
    ExecuteRunOut,
    FailureDetailsOut,
    KpiOut,
    RunAuditEventOut,
    RunDetailOut,
    RunListItemOut,
    SegmentBarOut,
    UpdateRunRequest,
    UploadOut,
    ValidateRunRequest,
    ValidationIssueOut,
    ValidationResultOut,
    hash_display,
    upload_to_input_file,
)
from app.modules.segments.models import Segment
from app.modules.tenants.models import Tenant
from app.tasks.compute_tasks import enqueue_compute_pipeline

_AUDIT_DISPLAY: dict[str, tuple[str, str, str]] = {
    AuditEvent.RUN_CREATED.value: ("accent", "Plus", "Run created"),
    AuditEvent.FILE_UPLOADED.value: ("default", "Upload", "Files uploaded"),
    AuditEvent.VALIDATION_TRIGGERED.value: ("default", "FileSearch", "Validation started"),
    AuditEvent.VALIDATION_COMPLETED.value: ("ok", "Check", "Validation passed"),
    AuditEvent.RUN_QUEUED.value: ("accent", "Zap", "Computation started"),
    AuditEvent.RUN_COMPLETED.value: ("ok", "Check", "Run completed"),
    AuditEvent.RUN_FAILED.value: ("err", "X", "Run failed"),
    AuditEvent.RUN_DELETED.value: ("default", "Trash2", "Run soft-deleted"),
}


def _default_engine_progress() -> dict[str, Any]:
    stage = {
        "status": "pending",
        "started_at": None,
        "finished_at": None,
        "elapsed_ms": None,
    }
    return {"pd": dict(stage), "lgd": dict(stage), "ead": dict(stage), "ecl": dict(stage)}


def _issue_id(issue: ValidationIssue) -> str:
    digest = hashlib.sha256(f"{issue.title}:{issue.location}".encode()).hexdigest()
    return digest[:12]


def _format_dt(dt: datetime | None, tz_name: str = "UTC") -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    local = dt.astimezone(ZoneInfo(tz_name))
    return local.strftime("%d %b %H:%M")


def _format_date(dt: datetime | None, tz_name: str = "UTC") -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    local = dt.astimezone(ZoneInfo(tz_name))
    return local.strftime("%d %b %Y")


def _format_time(dt: datetime | None, tz_name: str = "UTC") -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    local = dt.astimezone(ZoneInfo(tz_name))
    return local.strftime("%H:%M:%S")


def _format_elapsed(started_at: datetime | None, finished_at: datetime | None) -> str | None:
    if not started_at or not finished_at:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=UTC)
    seconds = int((finished_at - started_at).total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}m {secs}s" if secs else f"{minutes}m"


def _stage_out(data: dict[str, Any] | None) -> EngineStageProgressOut:
    data = data or {}
    return EngineStageProgressOut(
        status=data.get("status", "pending"),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        elapsed_ms=data.get("elapsed_ms"),
    )


def _engine_progress_out(progress: dict[str, Any] | None) -> EngineProgressOut | None:
    if not progress:
        return None
    return EngineProgressOut(
        pd=_stage_out(progress.get("pd")),
        lgd=_stage_out(progress.get("lgd")),
        ead=_stage_out(progress.get("ead")),
        ecl=_stage_out(progress.get("ecl")),
    )


async def _get_tenant(db: AsyncSession, tenant_id: str) -> Tenant:
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise ECLException("RESOURCE_NOT_FOUND", "Workspace not found.", 404)
    return tenant


async def _get_run(db: AsyncSession, tenant_id: str, run_id: str) -> Run:
    result = await db.execute(
        select(Run).where(
            Run.id == run_id,
            Run.tenant_id == tenant_id,
            Run.deleted_at.is_(None),
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise ECLException("RESOURCE_NOT_FOUND", "Run not found.", 404)
    return run


async def _get_user(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ECLException("RESOURCE_NOT_FOUND", "User not found.", 404)
    return user


async def _allowed_segments(db: AsyncSession, tenant_id: str) -> set[str]:
    result = await db.execute(
        select(Segment.name).where(
            Segment.tenant_id == tenant_id,
            Segment.deleted_at.is_(None),
        )
    )
    return {row[0] for row in result.all()}


async def _allowed_collateral(db: AsyncSession, tenant_id: str) -> set[str]:
    result = await db.execute(
        select(CollateralType.name).where(
            CollateralType.tenant_id == tenant_id,
            CollateralType.deleted_at.is_(None),
        )
    )
    return {row[0] for row in result.all()}


def _parse_excel(content: bytes) -> tuple[dict[str, pd.DataFrame], int, int]:
    buffer = io.BytesIO(content)
    sheets: dict[str, pd.DataFrame] = pd.read_excel(buffer, sheet_name=None, engine="openpyxl")
    row_count = sum(len(df) for df in sheets.values())
    return sheets, len(sheets), row_count


def _combine_sheets(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = [df for df in sheets.values() if not df.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


async def _load_uploads(db: AsyncSession, run_id: str) -> list[Upload]:
    result = await db.execute(
        select(Upload).where(Upload.run_id == run_id).order_by(Upload.created_at)
    )
    return list(result.scalars().all())


def _validation_status_from_issues(
    issues: list[ValidationIssue], *, warnings_accepted: bool
) -> str:
    if any(i.level == "block" for i in issues):
        return ValidationStatus.ERROR.value
    if any(i.level == "warn" for i in issues) and not warnings_accepted:
        return ValidationStatus.WARN.value
    return ValidationStatus.OK.value


def _issues_to_out(issues: list[ValidationIssue]) -> list[ValidationIssueOut]:
    return [
        ValidationIssueOut(
            id=_issue_id(issue),
            level=issue.level,
            title=issue.title,
            location=issue.location,
            fix=issue.fix,
        )
        for issue in issues
    ]


def _extract_segments(dfs: list[pd.DataFrame]) -> set[str]:
    found: set[str] = set()
    for df in dfs:
        if "SEGMENT" in df.columns:
            values = df["SEGMENT"].dropna().astype(str).str.strip()
            found.update(v for v in values if v)
    return found


async def _audit_events_for_run(
    db: AsyncSession,
    run_id: str,
    tz_name: str,
) -> list[RunAuditEventOut]:
    from app.modules.audit.models import AuditLog

    result = await db.execute(
        select(AuditLog, User)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.details["run_id"].as_string() == run_id)
        .order_by(AuditLog.created_at)
    )
    events: list[RunAuditEventOut] = []
    for log, user in result.all():
        kind, icon, title = _AUDIT_DISPLAY.get(
            log.event_type, ("default", "Clock", log.event_type)
        )
        details = log.details or {}
        description = str(details.get("description", details.get("message", "")))
        who = user.name if user else "system"
        events.append(
            RunAuditEventOut(
                id=log.id,
                kind=kind,  # type: ignore[arg-type]
                iconName=icon,
                title=title,
                description=description,
                who=who,
                time=_format_time(log.created_at, tz_name),
            )
        )
    return events


def _build_kpis(run: Run, loan_count: int | None = None) -> list[KpiOut]:
    if run.status != RunStatus.COMPLETE.value:
        return [
            KpiOut(id="total-ecl", label="Total ECL", currencyPrefix=None, value="—"),
            KpiOut(id="coverage", label="Coverage ratio", value="—"),
            KpiOut(id="outstanding", label="Total outstanding", currencyPrefix=None, value="—"),
            KpiOut(id="loans", label="Loans analysed", value="—"),
        ]
    total_ecl = float(run.total_ecl or 0)
    outstanding = float(run.total_outstanding or 0)
    coverage = format_coverage(float(run.coverage_ratio or 0)) if run.coverage_ratio else "—"
    loans_note = f"{loan_count:,} loans" if loan_count else None
    return [
        KpiOut(
            id="total-ecl",
            label="Total ECL",
            currencyPrefix=None,
            value=format_amount(total_ecl),
        ),
        KpiOut(
            id="coverage",
            label="Coverage ratio",
            helpText="ECL ÷ total outstanding",
            value=coverage,
        ),
        KpiOut(
            id="outstanding",
            label="Total outstanding",
            currencyPrefix=None,
            value=format_compact_amount(outstanding),
            subNote=loans_note,
        ),
        KpiOut(
            id="loans",
            label="Loans analysed",
            value=f"{loan_count:,}" if loan_count else "—",
        ),
    ]


async def _segment_bars(db: AsyncSession, run_id: str, tenant_id: str) -> list[SegmentBarOut]:
    from app.modules.results.models import EadResult

    result = await db.execute(
        select(EadResult.segment, func.sum(EadResult.discounted_ecl).label("ecl"))
        .where(EadResult.run_id == run_id, EadResult.tenant_id == tenant_id)
        .group_by(EadResult.segment)
        .order_by(func.sum(EadResult.discounted_ecl).desc())
        .limit(6)
    )
    return [
        SegmentBarOut(name=row.segment, value=float(row.ecl or 0)) for row in result.all()
    ]


def _engine_info(run: Run) -> EngineInfoOut:
    return EngineInfoOut(
        version=run.engine_version,
        releasedDate=ENGINE_RELEASED_DATE,
        pdMethod=PD_METHOD,
        lgdMethod=LGD_METHOD,
        eadMethod=EAD_METHOD,
        pdFilesCombined=run.combine_pd_files,
        deterministic=True,
    )


async def _input_files(
    db: AsyncSession, run_id: str, uploads: list[Upload] | None = None
) -> list[RunInputFileOut]:
    uploads = uploads or await _load_uploads(db, run_id)
    files: list[RunInputFileOut] = []
    for upload in uploads:
        warning_count = 0
        if upload.validation_status == ValidationStatus.WARN.value:
            warning_count = 1
        files.append(
            upload_to_input_file(
                kind=upload.kind,
                name=upload.original_filename,
                file_size_bytes=upload.file_size_bytes,
                sheet_count=upload.sheet_count,
                validation_status=upload.validation_status,
                warning_count=warning_count,
                sha256=upload.sha256,
            )
        )
    return files


async def _run_list_item(
    run: Run,
    user: User,
    tenant: Tenant,
) -> RunListItemOut:
    period = run.reporting_period or run.name
    coverage = (
        format_coverage(float(run.coverage_ratio))
        if run.coverage_ratio is not None and run.status == RunStatus.COMPLETE.value
        else None
    )
    return RunListItemOut(
        id=short_ulid(run.id),
        fullId=run.id,
        name=run.name,
        period=period,
        createdAt=_format_dt(run.created_at, tenant.timezone),
        byInitials=user_initials(user.name),
        byName=user.name,
        status=map_run_status_to_api(run.status),
        eclAmount=float(run.total_ecl) if run.total_ecl is not None else None,
        coverage=coverage,
        currency=tenant.currency,
    )


async def create_run(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    req: CreateRunRequest,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> RunDetailOut:
    await _get_tenant(db, tenant_id)
    user = await _get_user(db, user_id)
    run = Run(
        id=new_ulid(),
        tenant_id=tenant_id,
        created_by_user_id=user_id,
        name=req.name.strip(),
        reporting_period=req.reporting_period.strip() if req.reporting_period else None,
        status=RunStatus.DRAFT.value,
        engine_version=ENGINE_VERSION,
    )
    db.add(run)
    await db.flush()
    await log_event(
        db,
        AuditEvent.RUN_CREATED.value,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        details={"run_id": run.id, "description": "Draft initialised"},
    )
    return await get_run(db, tenant_id, run.id)


async def update_run(
    db: AsyncSession,
    tenant_id: str,
    run_id: str,
    req: UpdateRunRequest,
) -> RunDetailOut:
    run = await _get_run(db, tenant_id, run_id)
    if run.status not in (RunStatus.DRAFT.value, RunStatus.QUEUED.value):
        raise ECLException(
            "RUN_NOT_EDITABLE",
            "Run can only be updated while in draft or queued status.",
            409,
        )
    if req.combine_pd_files is not None:
        run.combine_pd_files = req.combine_pd_files
    if req.name is not None:
        run.name = req.name.strip()
    if req.reporting_period is not None:
        run.reporting_period = req.reporting_period.strip() or None
    await db.flush()
    return await get_run(db, tenant_id, run_id)


async def upload_file(
    db: AsyncSession,
    tenant_id: str,
    run_id: str,
    user_id: str,
    *,
    kind: str,
    filename: str,
    file_obj: Any,
    content_type: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> UploadOut:
    run = await _get_run(db, tenant_id, run_id)
    if run.status not in (RunStatus.DRAFT.value, RunStatus.FAILED.value):
        raise ECLException(
            "RUN_NOT_UPLOADABLE",
            "Files can only be uploaded to draft or failed runs.",
            409,
        )
    if kind not in {UploadKind.PD.value, UploadKind.LGD.value, UploadKind.EAD.value}:
        raise ECLException("INVALID_UPLOAD_KIND", "kind must be PD, LGD, or EAD.", 400)

    existing = await db.execute(
        select(Upload).where(Upload.run_id == run_id, Upload.kind == kind)
    )
    for old in existing.scalars().all():
        if kind != UploadKind.PD.value:
            await delete_object(old.storage_path)
            await db.delete(old)

    safe_name = filename.replace("/", "_").replace("\\", "_")
    storage_path = build_storage_path(tenant_id, run_id, kind.lower(), safe_name)
    sha256, size = await upload_stream(storage_path, file_obj, content_type)

    content = await download_bytes(storage_path)
    sheets, sheet_count, row_count = _parse_excel(content)

    upload = Upload(
        id=new_ulid(),
        run_id=run_id,
        tenant_id=tenant_id,
        kind=kind,
        original_filename=filename,
        sha256=sha256,
        storage_path=storage_path,
        file_size_bytes=size,
        sheet_count=sheet_count,
        row_count=row_count,
    )
    db.add(upload)
    await db.flush()
    await log_event(
        db,
        AuditEvent.FILE_UPLOADED.value,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        details={
            "run_id": run_id,
            "description": f"{filename} {hash_display(sha256)}",
            "kind": kind,
            "filename": filename,
        },
    )
    return UploadOut(
        id=upload.id,
        kind=kind,
        original_filename=filename,
        file_size=format_file_size(size),
        sha256=sha256,
        sheet_count=sheet_count,
        row_count=row_count,
    )


async def validate_files(
    db: AsyncSession,
    tenant_id: str,
    run_id: str,
    user_id: str,
    req: ValidateRunRequest,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> ValidationResultOut:
    await _get_run(db, tenant_id, run_id)
    uploads = await _load_uploads(db, run_id)
    if not uploads:
        raise ECLException("NO_UPLOADS", "No files uploaded for this run.", 400)

    await log_event(
        db,
        AuditEvent.VALIDATION_TRIGGERED.value,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        details={"run_id": run_id, "description": "Validation started"},
    )

    allowed_segments = await _allowed_segments(db, tenant_id)
    allowed_collateral = await _allowed_collateral(db, tenant_id)
    accepted_ids = set(req.accepted_warning_ids)

    all_issues: list[ValidationIssue] = []
    segment_dfs: list[pd.DataFrame] = []

    for upload in uploads:
        content = await download_bytes(upload.storage_path)
        sheets, _, _ = _parse_excel(content)
        combined = _combine_sheets(sheets)
        issues: list[ValidationIssue] = []

        if upload.kind == UploadKind.PD.value:
            for sheet_name, df in sheets.items():
                result = validate_pd(df, sheet_name=sheet_name, allowed_segments=allowed_segments)
                issues.extend(result.issues)
            segment_dfs.append(combined)
        elif upload.kind == UploadKind.LGD.value:
            for sheet_name, df in sheets.items():
                result = validate_lgd(
                    df,
                    sheet_name=sheet_name,
                    allowed_collateral_types=allowed_collateral,
                )
                issues.extend(result.issues)
        elif upload.kind == UploadKind.EAD.value:
            for sheet_name, df in sheets.items():
                result = validate_ead(df, sheet_name=sheet_name, allowed_segments=allowed_segments)
                issues.extend(result.issues)
            segment_dfs.append(combined)

        upload_warnings_accepted = upload.warnings_accepted
        if req.accepted_warning_ids:
            upload_warning_ids = {_issue_id(i) for i in issues if i.level == "warn"}
            if upload_warning_ids and upload_warning_ids.issubset(accepted_ids):
                upload.warnings_accepted = True
                upload_warnings_accepted = True
            elif not any(i.level == "block" for i in issues):
                warn_ids = {_issue_id(i) for i in issues if i.level == "warn"}
                if warn_ids & accepted_ids:
                    upload.warnings_accepted = True
                    upload_warnings_accepted = True

        upload.validation_status = _validation_status_from_issues(
            issues, warnings_accepted=upload_warnings_accepted
        )
        all_issues.extend(issues)

    detected = sorted(_extract_segments(segment_dfs))
    overall_status = ValidationStatus.OK.value
    if any(i.level == "block" for i in all_issues):
        overall_status = ValidationStatus.ERROR.value
    elif any(i.level == "warn" for i in all_issues):
        unaccepted = [
            i
            for i in all_issues
            if i.level == "warn" and _issue_id(i) not in accepted_ids
        ]
        if unaccepted and not all(u.warnings_accepted for u in uploads):
            overall_status = ValidationStatus.WARN.value

    await db.flush()
    await log_event(
        db,
        AuditEvent.VALIDATION_COMPLETED.value,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        details={
            "run_id": run_id,
            "description": f"Validation {overall_status} · {len(detected)} segments detected",
            "status": overall_status,
        },
    )
    return ValidationResultOut(
        status=overall_status,  # type: ignore[arg-type]
        issues=_issues_to_out(all_issues),
        detected_segments=detected,
    )


async def execute_run(
    db: AsyncSession,
    tenant_id: str,
    run_id: str,
    user_id: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> ExecuteRunOut:
    run = await _get_run(db, tenant_id, run_id)
    if run.status not in (RunStatus.DRAFT.value, RunStatus.FAILED.value):
        raise ECLException("RUN_NOT_EXECUTABLE", "Run is not in an executable state.", 409)

    uploads = await _load_uploads(db, run_id)
    kinds = {u.kind for u in uploads}
    required = {UploadKind.PD.value, UploadKind.LGD.value, UploadKind.EAD.value}
    if not required.issubset(kinds):
        missing = ", ".join(sorted(required - kinds))
        raise ECLException(
            "MISSING_UPLOADS",
            f"Missing required uploads: {missing}.",
            400,
        )

    for upload in uploads:
        if upload.validation_status not in (
            ValidationStatus.OK.value,
            ValidationStatus.WARN.value,
        ):
            raise ECLException(
                "VALIDATION_REQUIRED",
                f"Upload {upload.original_filename} has not passed validation.",
                400,
            )
        if upload.validation_status == ValidationStatus.WARN.value and not upload.warnings_accepted:
            raise ECLException(
                "WARNINGS_NOT_ACCEPTED",
                "Accept validation warnings before executing.",
                400,
            )

    run.status = RunStatus.QUEUED.value
    run.engine_progress = _default_engine_progress()
    run.failure_stage = None
    run.failure_message = None
    run.failure_ref = None
    run.started_at = None
    run.finished_at = None
    await db.flush()

    enqueue_compute_pipeline.delay(run_id)

    await log_event(
        db,
        AuditEvent.RUN_QUEUED.value,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        details={
            "run_id": run_id,
            "description": f"Engine {run.engine_version}",
        },
    )
    return ExecuteRunOut(run_id=run_id, status="queued")


async def get_run(
    db: AsyncSession,
    tenant_id: str,
    run_id: str,
    user: User | None = None,
    membership: TenantMembership | None = None,
) -> RunDetailOut:
    tenant = await _get_tenant(db, tenant_id)
    if user is not None:
        run = await assert_run_visible(db, user, tenant_id, membership, run_id)
    else:
        result = await db.execute(
            select(Run).where(Run.id == run_id, Run.tenant_id == tenant_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            raise ECLException("RESOURCE_NOT_FOUND", "Run not found.", 404)

    user = await _get_user(db, run.created_by_user_id)
    base = await _run_list_item(run, user, tenant)

    from app.modules.results.models import EadResult

    loan_count_result = await db.execute(
        select(func.count(func.distinct(EadResult.loan_id))).where(
            EadResult.run_id == run_id,
            EadResult.tenant_id == tenant_id,
        )
    )
    loan_count = loan_count_result.scalar_one_or_none()

    deleted_by_name: str | None = None
    if run.deleted_by_user_id:
        deleter = await _get_user(db, run.deleted_by_user_id)
        deleted_by_name = deleter.name

    failure: FailureDetailsOut | None = None
    if run.failure_stage and run.failure_message:
        failure = FailureDetailsOut(
            stage=run.failure_stage,
            message=run.failure_message,
            ref=run.failure_ref or "",
        )

    accepted_warnings = sum(1 for u in await _load_uploads(db, run_id) if u.warnings_accepted)

    return RunDetailOut(
        **base.model_dump(),
        elapsed=_format_elapsed(run.started_at, run.finished_at),
        kpis=_build_kpis(run, loan_count),
        segments=await _segment_bars(db, run_id, tenant_id)
        if run.status == RunStatus.COMPLETE.value
        else [],
        inputFiles=await _input_files(db, run_id),
        auditEvents=await _audit_events_for_run(db, run_id, tenant.timezone),
        engineInfo=_engine_info(run),
        engineProgress=_engine_progress_out(run.engine_progress),
        failureDetails=failure,
        deletedBy=deleted_by_name,
        deletedAt=_format_date(run.deleted_at, tenant.timezone) if run.deleted_at else None,
        acceptedWarnings=accepted_warnings or None,
    )


async def list_runs(
    db: AsyncSession,
    tenant_id: str,
    *,
    user: User | None = None,
    membership: TenantMembership | None = None,
    page: int = 1,
    per_page: int = 50,
    status: str | None = None,
    search: str | None = None,
) -> tuple[list[RunListItemOut], PageMeta]:
    tenant = await _get_tenant(db, tenant_id)
    if user is not None:
        scope = get_run_scope_filter(user, tenant_id, membership)
        base = (
            select(Run, User)
            .join(User, User.id == Run.created_by_user_id)
            .where(scope, Run.deleted_at.is_(None))
        )
    else:
        base = (
            select(Run, User)
            .join(User, User.id == Run.created_by_user_id)
            .where(Run.tenant_id == tenant_id, Run.deleted_at.is_(None))
        )

    if status and status != "all":
        status_values: list[str] = []
        for token in status.split(","):
            token = token.strip()
            if token == "running":
                status_values.extend(
                    [
                        RunStatus.PD_RUNNING.value,
                        RunStatus.LGD_RUNNING.value,
                        RunStatus.EAD_RUNNING.value,
                        RunStatus.QUEUED.value,
                    ]
                )
            elif token == "success":
                status_values.append(RunStatus.COMPLETE.value)
            elif token == "draft":
                status_values.append(RunStatus.DRAFT.value)
            elif token == "failed":
                status_values.append(RunStatus.FAILED.value)
            elif token == "queued":
                status_values.append(RunStatus.QUEUED.value)
            elif token == "deleted":
                status_values.append(RunStatus.DELETED.value)
            else:
                status_values.append(token)
        if status_values:
            base = base.where(Run.status.in_(status_values))

    if search:
        pattern = f"%{search.strip()}%"
        base = base.where(
            or_(Run.name.ilike(pattern), Run.reporting_period.ilike(pattern))
        )

    count_q = select(func.count()).select_from(
        base.with_only_columns(Run.id).subquery()
    )
    total = (await db.execute(count_q)).scalar_one()
    offset = (page - 1) * per_page
    result = await db.execute(
        base.order_by(Run.created_at.desc()).offset(offset).limit(per_page)
    )
    pages = max(1, (total + per_page - 1) // per_page)
    meta = PageMeta(
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )
    items = [
        await _run_list_item(run, user, tenant) for run, user in result.all()
    ]
    return items, meta


async def delete_run(
    db: AsyncSession,
    tenant_id: str,
    run_id: str,
    user_id: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    run = await _get_run(db, tenant_id, run_id)
    run.deleted_at = datetime.now(UTC)
    run.deleted_by_user_id = user_id
    run.status = RunStatus.DELETED.value
    await db.flush()
    await log_event(
        db,
        AuditEvent.RUN_DELETED.value,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        details={"run_id": run_id, "description": "Retained for audit"},
    )
