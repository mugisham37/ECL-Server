from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_ulid
from app.database import Base


class NotificationPreferences(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    user_id: Mapped[str] = mapped_column(String(26), nullable=False, unique=True, index=True)
    run_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    run_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    weekly_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    member_joined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    product_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
