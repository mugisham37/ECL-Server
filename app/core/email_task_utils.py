"""Shared helpers for Celery email tasks."""

from __future__ import annotations

import smtplib
from typing import TYPE_CHECKING, Any

from jinja2 import TemplateError

if TYPE_CHECKING:
    from celery.app.task import Task


def is_transient_email_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError, OSError, smtplib.SMTPServerDisconnected)):
        return True
    cause = exc.__cause__
    transient = (TimeoutError, ConnectionError, OSError, smtplib.SMTPServerDisconnected)
    return isinstance(cause, transient)


def is_auth_email_error(exc: BaseException) -> bool:
    if isinstance(exc, (smtplib.SMTPAuthenticationError, smtplib.SMTPNotSupportedError)):
        return True
    cause = exc.__cause__
    return isinstance(cause, (smtplib.SMTPAuthenticationError, smtplib.SMTPNotSupportedError))


def handle_email_task_exception(
    task: Task[Any, Any],
    exc: BaseException,
    *,
    task_name: str,
    **log_context: object,
) -> None:
    from app.core.logging import get_logger

    log = get_logger("email")

    if isinstance(exc, TemplateError):
        log.error(
            "email_send_failed",
            task=task_name,
            category="template",
            exc=str(exc),
            exc_info=True,
            **log_context,
        )
        return

    if is_auth_email_error(exc):
        log.error(
            "email_send_failed",
            task=task_name,
            category="auth",
            exc=str(exc),
            exc_info=True,
            **log_context,
        )
        raise exc

    if is_transient_email_error(exc):
        retries = task.request.retries
        log.warning(
            "email_send_retry",
            task=task_name,
            category="transient",
            retries=retries,
            exc=str(exc),
            exc_info=True,
            **log_context,
        )
        raise task.retry(countdown=30, max_retries=3, exc=exc)

    log.error(
        "email_send_failed",
        task=task_name,
        category="unknown",
        exc=str(exc),
        exc_info=True,
        **log_context,
    )
    raise exc
