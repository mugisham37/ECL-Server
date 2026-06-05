from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Index, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("runs_tenant_status_idx", "tenant_id", "status"),
        Index("runs_tenant_created_idx", "tenant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(String(26), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    reporting_period: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    engine_version: Mapped[str] = mapped_column(Text, nullable=False, server_default="v1.0.0")
    engine_progress: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    combine_pd_files: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    failure_stage: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_ecl: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    total_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    coverage_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    run_warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(String(26), nullable=True)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sheet_count: Mapped[int | None] = mapped_column(nullable=True)
    row_count: Mapped[int | None] = mapped_column(nullable=True)
    validation_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
