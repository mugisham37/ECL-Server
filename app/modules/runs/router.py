from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.core.limiter import limiter
from app.dependencies import (
    CurrentUser,
    DbSession,
    get_client_ip,
    get_user_agent,
    require_tenant_admin,
    require_tenant_analyst_or_admin,
    require_tenant_member,
)
from app.modules.runs import service
from app.modules.runs.schemas import (
    CreateRunRequest,
    ExecuteRunResponse,
    PresignedDownloadResponse,
    RunListResponse,
    RunResponse,
    UpdateRunRequest,
    UploadResponse,
    ValidateRunRequest,
    ValidationResponse,
)
from app.modules.results import service as results_service
from app.modules.tenants.models import TenantMembership

router = APIRouter(prefix="/tenants", tags=["runs"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "static" / "templates"


@router.post("/{tenant_id}/runs", status_code=status.HTTP_201_CREATED)
async def create_run_endpoint(
    tenant_id: str,
    body: CreateRunRequest,
    request: Request,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_analyst_or_admin),
) -> RunResponse:
    data = await service.create_run(
        db,
        tenant_id,
        user.id,
        body,
        ip=get_client_ip(request.headers.get("X-Forwarded-For")),
        user_agent=get_user_agent(request.headers.get("User-Agent")),
    )
    return RunResponse(data=data)


@router.patch("/{tenant_id}/runs/{run_id}")
async def update_run_endpoint(
    tenant_id: str,
    run_id: str,
    body: UpdateRunRequest,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_analyst_or_admin),
) -> RunResponse:
    data = await service.update_run(db, tenant_id, run_id, body)
    return RunResponse(data=data)


@router.post("/{tenant_id}/runs/{run_id}/uploads", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def upload_file_endpoint(
    request: Request,
    tenant_id: str,
    run_id: str,
    db: DbSession,
    user: CurrentUser,
    kind: str = Form(...),
    file: UploadFile = File(...),
    _a: TenantMembership = Depends(require_tenant_analyst_or_admin),
) -> UploadResponse:
    data = await service.upload_file(
        db,
        tenant_id,
        run_id,
        user.id,
        kind=kind.upper(),
        filename=file.filename or "upload.xlsx",
        file_obj=file.file,
        content_type=file.content_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ip=get_client_ip(request.headers.get("X-Forwarded-For")),
        user_agent=get_user_agent(request.headers.get("User-Agent")),
    )
    return UploadResponse(data=data)


@router.post("/{tenant_id}/runs/{run_id}/validate")
async def validate_files_endpoint(
    tenant_id: str,
    run_id: str,
    body: ValidateRunRequest,
    request: Request,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_analyst_or_admin),
) -> ValidationResponse:
    data = await service.validate_files(
        db,
        tenant_id,
        run_id,
        user.id,
        body,
        ip=get_client_ip(request.headers.get("X-Forwarded-For")),
        user_agent=get_user_agent(request.headers.get("User-Agent")),
    )
    return ValidationResponse(data=data)


@router.post(
    "/{tenant_id}/runs/{run_id}/execute",
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_run_endpoint(
    tenant_id: str,
    run_id: str,
    request: Request,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_analyst_or_admin),
) -> ExecuteRunResponse:
    data = await service.execute_run(
        db,
        tenant_id,
        run_id,
        user.id,
        ip=get_client_ip(request.headers.get("X-Forwarded-For")),
        user_agent=get_user_agent(request.headers.get("User-Agent")),
    )
    return ExecuteRunResponse(data=data)


@router.get("/{tenant_id}/runs/{run_id}")
async def get_run_endpoint(
    tenant_id: str,
    run_id: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
) -> RunResponse:
    data = await service.get_run(db, tenant_id, run_id)
    return RunResponse(data=data)


@router.get("/{tenant_id}/runs")
async def list_runs_endpoint(
    tenant_id: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> RunListResponse:
    items, meta = await service.list_runs(
        db,
        tenant_id,
        page=page,
        per_page=per_page,
        status=status,
        search=search,
    )
    return RunListResponse(data=items, meta=meta.model_dump())


@router.delete("/{tenant_id}/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run_endpoint(
    tenant_id: str,
    run_id: str,
    request: Request,
    db: DbSession,
    user: CurrentUser,
    _a: TenantMembership = Depends(require_tenant_admin),
) -> None:
    await service.delete_run(
        db,
        tenant_id,
        run_id,
        user.id,
        ip=get_client_ip(request.headers.get("X-Forwarded-For")),
        user_agent=get_user_agent(request.headers.get("User-Agent")),
    )


@router.get("/{tenant_id}/runs/{run_id}/downloads/{kind}")
async def download_artifact_endpoint(
    tenant_id: str,
    run_id: str,
    kind: str,
    db: DbSession,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
) -> PresignedDownloadResponse:
    url, expires_at = await results_service.get_presigned_download(
        db, tenant_id, run_id, kind.upper()
    )
    from app.modules.runs.schemas import PresignedDownloadOut

    return PresignedDownloadResponse(
        data=PresignedDownloadOut(url=url, expires_at=expires_at)
    )


@router.get("/{tenant_id}/templates/{kind}")
async def get_template_endpoint(
    tenant_id: str,
    kind: str,
    user: CurrentUser,
    _m: TenantMembership = Depends(require_tenant_member),
) -> FileResponse:
    kind_upper = kind.upper()
    if kind_upper not in {"PD", "LGD", "EAD"}:
        from app.core.exceptions import ECLException

        raise ECLException("INVALID_TEMPLATE_KIND", "Template kind must be PD, LGD, or EAD.", 400)
    path = _TEMPLATES_DIR / f"{kind_upper}.xlsx"
    if not path.is_file():
        from app.core.exceptions import ECLException

        raise ECLException("TEMPLATE_NOT_FOUND", f"Template {kind_upper} not found.", 404)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"ECL_{kind_upper}_template.xlsx",
    )
