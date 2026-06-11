"""SQLAlchemy session hooks for deferring side effects until after commit."""

from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.logging import get_logger

_log = get_logger("db.hooks")
_listeners_installed = False


def _ensure_listener() -> None:
    global _listeners_installed
    if _listeners_installed:
        return

    @event.listens_for(Session, "after_commit")
    def _run_after_commit(session: Session) -> None:
        callbacks = session.info.pop("after_commit_callbacks", [])
        if callbacks:
            _log.debug("db_after_commit_callbacks_firing", count=len(callbacks))
        for fn in callbacks:
            fn()

    _listeners_installed = True


def run_after_commit(session: AsyncSession, fn: Callable[[], None]) -> None:
    """Schedule fn to run after the session's next successful commit."""
    _ensure_listener()
    session.sync_session.info.setdefault("after_commit_callbacks", []).append(fn)
