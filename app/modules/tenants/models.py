from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="trial")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="trial")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    reporting_cadence: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    onboarding_progress: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    mrr_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    engine_version_pin: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_requested_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
