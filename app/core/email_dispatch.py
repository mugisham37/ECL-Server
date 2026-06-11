"""Email dispatch helpers.

Two strategies:
- dispatch_celery_task_after_commit: legacy after-commit hook (kept for non-email use)
- queue_email_in_outbox: preferred — writes to email_outbox in the same DB transaction
  so the intent survives Redis downtime and process restarts.
"""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db_hooks import run_after_commit
from app.core.logging import get_logger

_log = get_logger("email")


def dispatch_celery_task_after_commit(
    db: AsyncSession,
    *,
    task_name: str,
    dispatch: Callable[[], object],
    **log_context: object,
) -> None:
    """Queue a Celery task only after the current session commits successfully."""

    def _dispatch() -> None:
        try:
            dispatch()
            _log.info("email_task_dispatched", task=task_name, **log_context)
        except Exception as exc:
            _log.warning(
                "email_task_dispatch_failed",
                task=task_name,
                exc=str(exc),
                exc_info=True,
                **log_context,
            )

    _log.debug("email_dispatch_callback_registered", task=task_name, **log_context)
    run_after_commit(db, _dispatch)


def queue_email_in_outbox(
    db: AsyncSession,
    *,
    task_name: str,
    payload: dict,  # type: ignore[type-arg]
) -> None:
    """Write an email task to the outbox table within the current DB transaction.

    The row is committed atomically with the calling transaction.  The
    process_email_outbox beat task (every 30 s) dispatches pending rows to Celery.
    If Redis is down the row stays pending and is retried automatically.
    """
    from app.core.security import new_ulid
    from app.modules.email_outbox.models import EmailOutbox

    entry = EmailOutbox(id=new_ulid(), task_name=task_name, payload=payload)
    db.add(entry)
    _log.debug("email_outbox_queued", task=task_name, payload_keys=list(payload.keys()))
