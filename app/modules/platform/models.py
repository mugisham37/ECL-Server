from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_ulid
from app.database import Base


class EngineVersion(Base):
    __tablename__ = "engine_versions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    version: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    changelog: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by_user_id: Mapped[str] = mapped_column(String(26), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ImpersonationSession(Base):
    __tablename__ = "impersonation_sessions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    platform_user_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    target_tenant_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
