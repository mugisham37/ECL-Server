from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_by_user_id: Mapped[str] = mapped_column(String(26), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
