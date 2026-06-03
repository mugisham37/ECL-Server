from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    detail: str
    field: str | None = None
    retry_after: int | None = None


class ECLException(Exception):
    def __init__(
        self,
        code: str,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        field: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.field = field
        self.retry_after = retry_after
        super().__init__(detail)


class InvalidCredentialsError(ECLException):
    def __init__(self) -> None:
        super().__init__(
            "INVALID_CREDENTIALS",
            "Invalid email or password.",
            status.HTTP_401_UNAUTHORIZED,
        )


class AccountDisabledError(ECLException):
    def __init__(self) -> None:
        super().__init__(
            "ACCOUNT_DISABLED",
            "Your account has been disabled. Contact support.",
            status.HTTP_403_FORBIDDEN,
        )


class AccountLockedError(ECLException):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            "ACCOUNT_LOCKED",
            "Account locked due to too many failed login attempts.",
            status.HTTP_423_LOCKED,
            retry_after=retry_after,
        )


class EmailTakenError(ECLException):
    def __init__(self) -> None:
        super().__init__(
            "EMAIL_TAKEN",
            "This email is already registered.",
            status.HTTP_409_CONFLICT,
            field="email",
        )


class SlugTakenError(ECLException):
    def __init__(self) -> None:
        super().__init__(
            "SLUG_TAKEN",
            "A workspace with this name already exists.",
            status.HTTP_409_CONFLICT,
            field="company_name",
        )


class RateLimitedError(ECLException):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            "RATE_LIMITED",
            "Too many requests. Please wait before trying again.",
            status.HTTP_429_TOO_MANY_REQUESTS,
            retry_after=retry_after,
        )


def _error_body(exc: ECLException) -> dict[str, Any]:
    body: dict[str, Any] = {
        "code": exc.code,
        "detail": exc.detail,
        "field": exc.field,
    }
    if exc.retry_after is not None:
        body["retry_after"] = exc.retry_after
    return body


async def ecl_exception_handler(_request: Request, exc: ECLException) -> JSONResponse:
    headers: dict[str, str] = {}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc),
        headers=headers,
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = first.get("loc", ())
    field = str(loc[-1]) if loc else None
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "detail": first.get("msg", "Validation failed."),
            "field": field,
        },
    )


async def generic_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_ERROR",
            "detail": "An unexpected error occurred.",
            "field": None,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    from app.config import get_settings as _gs

    app.add_exception_handler(ECLException, ecl_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    if not _gs().debug:
        app.add_exception_handler(Exception, generic_exception_handler)
