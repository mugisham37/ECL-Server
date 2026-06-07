from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.engine.format_utils import format_file_size, short_ulid


class CreateRunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    reporting_period: str | None = Field(default=None, max_length=100)


class UpdateRunRequest(BaseModel):
    combine_pd_files: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    reporting_period: str | None = Field(default=None, max_length=100)


class RerunRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)


class UploadOut(BaseModel):
    id: str
    kind: str
    filename: str
    size_bytes: int
    sha256: str
    sheet_count: int | None = None
    row_count: int | None = None


class ValidationIssueOut(BaseModel):
    id: str
    kind: Literal["PD", "LGD", "EAD"]
    level: Literal["warn", "block"]
    title: str
    location: str
    fix: str


class ValidationResultOut(BaseModel):
    status: Literal["ok", "warn", "blocking"]
    issues: list[ValidationIssueOut]
    detected_segments: list[str]


class ValidateRunRequest(BaseModel):
    accepted_warning_ids: list[str] = Field(default_factory=list)


class RunListItemOut(BaseModel):
    id: str
    fullId: str
    name: str
    period: str
    createdAt: str
    byInitials: str
    byName: str
    status: str
    eclAmount: float | None
    coverage: str | None
    currency: str


class EngineStageProgressOut(BaseModel):
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_ms: int | None = None


class EngineProgressOut(BaseModel):
    pd: EngineStageProgressOut
    lgd: EngineStageProgressOut
    ead: EngineStageProgressOut
    ecl: EngineStageProgressOut


class RunInputFileOut(BaseModel):
    type: Literal["PD", "LGD", "EAD"]
    name: str
    size: str
    sheets: int
    validationStatus: Literal["ok", "warn", "error"]
    warningCount: int | None = None
    hash: str


class RunAuditEventOut(BaseModel):
    id: str
    kind: Literal["ok", "err", "accent", "default"]
    iconName: str
    title: str
    description: str
    who: str
    time: str


class EngineInfoOut(BaseModel):
    version: str
    releasedDate: str
    pdMethod: str
    lgdMethod: str
    eadMethod: str
    pdFilesCombined: bool
    deterministic: bool


class FailureDetailsOut(BaseModel):
    stage: str
    message: str
    ref: str


class KpiOut(BaseModel):
    id: str
    label: str
    helpText: str | None = None
    currencyPrefix: str | None = None
    value: str
    delta: float | None = None
    deltaDir: Literal["up", "down", "flat"] | None = None
    subNote: str | None = None
    staleAsOf: str | None = None


class SegmentBarOut(BaseModel):
    name: str
    value: float


class RunDetailOut(RunListItemOut):
    elapsed: str | None = None
    kpis: list[KpiOut]
    segments: list[SegmentBarOut]
    inputFiles: list[RunInputFileOut]
    auditEvents: list[RunAuditEventOut]
    engineInfo: EngineInfoOut
    engineProgress: EngineProgressOut | None = None
    failureDetails: FailureDetailsOut | None = None
    deletedBy: str | None = None
    deletedAt: str | None = None
    acceptedWarnings: int | None = None


class ExecuteRunOut(BaseModel):
    run_id: str
    status: str


class PresignedDownloadOut(BaseModel):
    url: str
    expires_at: datetime


class RunResponse(BaseModel):
    data: RunDetailOut


class RunListResponse(BaseModel):
    data: list[RunListItemOut]
    meta: dict[str, Any]


class UploadResponse(BaseModel):
    data: UploadOut


class ValidationResponse(BaseModel):
    data: ValidationResultOut


class ExecuteRunResponse(BaseModel):
    data: ExecuteRunOut


class PresignedDownloadResponse(BaseModel):
    data: PresignedDownloadOut


def hash_display(sha256: str) -> str:
    return short_ulid(sha256)


def upload_to_input_file(
    *,
    kind: str,
    name: str,
    file_size_bytes: int,
    sheet_count: int | None,
    validation_status: str | None,
    warning_count: int,
    sha256: str,
) -> RunInputFileOut:
    status: Literal["ok", "warn", "error"] = "ok"
    if validation_status == "error":
        status = "error"
    elif validation_status == "warn":
        status = "warn"
    return RunInputFileOut(
        type=kind,  # type: ignore[arg-type]
        name=name,
        size=format_file_size(file_size_bytes),
        sheets=sheet_count or 1,
        validationStatus=status,
        warningCount=warning_count if warning_count else None,
        hash=hash_display(sha256),
    )
