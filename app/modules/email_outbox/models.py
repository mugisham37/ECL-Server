from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EmailOutbox(Base):
    """Transactional outbox for email tasks.

    Written in the same DB transaction as the triggering event (signup, invite, etc.)
    so the email intent is never lost even if Redis or the Celery worker is down.
    The process_email_outbox beat task polls every 30 s and dispatches pending rows
    to Celery.  Once pushed to Redis, status moves to 'dispatched'; after 5 failed
    attempts it moves to 'dead_letter'.
    """

    __tablename__ = "email_outbox"

    __table_args__ = (
        Index("ix_email_outbox_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_dispatch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
