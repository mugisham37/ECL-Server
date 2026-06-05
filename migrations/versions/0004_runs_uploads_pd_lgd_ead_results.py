"""runs, uploads, pd/lgd/ead results, output artifacts

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("created_by_user_id", sa.String(26), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("reporting_period", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("engine_version", sa.Text(), nullable=False, server_default="v1.0.0"),
        sa.Column("engine_progress", sa.JSON(), nullable=True),
        sa.Column("combine_pd_files", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("failure_stage", sa.Text(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("failure_ref", sa.Text(), nullable=True),
        sa.Column("total_ecl", sa.Numeric(20, 6), nullable=True),
        sa.Column("total_outstanding", sa.Numeric(20, 6), nullable=True),
        sa.Column("coverage_ratio", sa.Numeric(10, 6), nullable=True),
        sa.Column("run_warnings", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.String(26), nullable=True),
    )
    op.create_index("runs_tenant_status_idx", "runs", ["tenant_id", "status"])
    op.create_index("runs_tenant_created_idx", "runs", ["tenant_id", "created_at"])
    op.create_index("runs_tenant_idx", "runs", ["tenant_id"])
    op.execute(
        "CREATE TRIGGER runs_updated_at BEFORE UPDATE ON runs "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    op.create_table(
        "uploads",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("run_id", sa.String(26), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sheet_count", sa.Integer(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("validation_status", sa.Text(), nullable=True),
        sa.Column("warnings_accepted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("uploads_run_idx", "uploads", ["run_id"])
    op.create_index("uploads_tenant_idx", "uploads", ["tenant_id"])

    op.create_table(
        "pd_results",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("run_id", sa.String(26), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("segment", sa.Text(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("transition", sa.Text(), nullable=False),
        sa.Column("s1_prob", sa.Numeric(10, 8), nullable=False),
        sa.Column("s2_prob", sa.Numeric(10, 8), nullable=False),
        sa.Column("s3_prob", sa.Numeric(10, 8), nullable=False),
        sa.Column("marginal_pd", sa.Numeric(10, 8), nullable=False),
        sa.Column("cure_rate", sa.Numeric(10, 8), nullable=False),
        sa.UniqueConstraint("run_id", "segment", "month", "transition", name="pd_results_unique"),
    )
    op.create_index("pd_results_run_idx", "pd_results", ["run_id"])
    op.create_index("pd_results_run_segment_idx", "pd_results", ["run_id", "segment"])

    op.create_table(
        "lgd_results",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("run_id", sa.String(26), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("loan_id", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column("eir", sa.Numeric(10, 8), nullable=False),
        sa.Column("sum_discounted_collat", sa.Numeric(20, 6), nullable=False),
        sa.UniqueConstraint("run_id", "loan_id", name="lgd_results_unique"),
    )
    op.create_index("lgd_results_run_idx", "lgd_results", ["run_id"])
    op.create_index("lgd_results_run_tenant_idx", "lgd_results", ["run_id", "tenant_id"])

    op.create_table(
        "ead_results",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("run_id", sa.String(26), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("loan_id", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column("segment", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("period_since_orig", sa.Integer(), nullable=False),
        sa.Column("period_to_discount", sa.Integer(), nullable=False),
        sa.Column("monthly_instalment", sa.Numeric(20, 6), nullable=False),
        sa.Column("bal_after_repayment", sa.Numeric(20, 6), nullable=False),
        sa.Column("bal_after_missed", sa.Numeric(20, 6), nullable=False),
        sa.Column("marginal_pd", sa.Numeric(10, 8), nullable=True),
        sa.Column("lgw", sa.Numeric(10, 8), nullable=False),
        sa.Column("lgd", sa.Numeric(10, 8), nullable=False),
        sa.Column("credit_loss", sa.Numeric(20, 6), nullable=False),
        sa.Column("discounted_ecl", sa.Numeric(20, 6), nullable=False),
    )
    op.create_index("ead_results_run_idx", "ead_results", ["run_id"])
    op.create_index("ead_results_run_loan_idx", "ead_results", ["run_id", "loan_id"])
    op.create_index("ead_results_run_segment_idx", "ead_results", ["run_id", "segment"])

    op.create_table(
        "output_artifacts",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("run_id", sa.String(26), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("output_artifacts_run_idx", "output_artifacts", ["run_id"])


def downgrade() -> None:
    for table in (
        "output_artifacts",
        "ead_results",
        "lgd_results",
        "pd_results",
        "uploads",
        "runs",
    ):
        op.drop_table(table)
