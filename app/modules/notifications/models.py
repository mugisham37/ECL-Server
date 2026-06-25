"""User in-app notifications."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_ulid
from app.database import Base


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
