"""management layer — notification prefs, engine versions, impersonation, columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users columns ────────────────────────────────────────────────────────
    op.add_column("users", sa.Column("title", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("avatar_storage_path", sa.Text(), nullable=True))

    # ── segments columns ─────────────────────────────────────────────────────
    op.add_column(
        "segments",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # ── tenants columns ──────────────────────────────────────────────────────
    op.add_column("tenants", sa.Column("region", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("mrr_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("tenants", sa.Column("engine_version_pin", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("close_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("close_requested_by", sa.String(26), nullable=True))

    # ── audit_logs tenant_id ─────────────────────────────────────────────────
    op.add_column("audit_logs", sa.Column("tenant_id", sa.String(26), nullable=True))
    op.create_index("audit_tenant_id_idx", "audit_logs", ["tenant_id"])

    # ── notification_preferences ───────────────────────────────────────────────
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), nullable=False, unique=True),
        sa.Column("run_completed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("run_failed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("weekly_summary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("member_joined", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("product_updates", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("notification_preferences_user_id_idx", "notification_preferences", ["user_id"])
    op.execute(
        "CREATE TRIGGER notification_preferences_updated_at BEFORE UPDATE ON notification_preferences "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ── engine_versions ──────────────────────────────────────────────────────
    op.create_table(
        "engine_versions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("version", sa.Text(), nullable=False, unique=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("changelog", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by_user_id", sa.String(26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("engine_versions_is_current_idx", "engine_versions", ["is_current"])
    op.execute(
        "CREATE TRIGGER engine_versions_updated_at BEFORE UPDATE ON engine_versions "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    op.execute(
        """
        INSERT INTO engine_versions (id, version, is_current, release_date, changelog, created_by_user_id, created_at, updated_at)
        VALUES (
            '01J00000000000000000000001',
            'v1.0.0',
            true,
            CURRENT_DATE,
            '["Initial GA release — PD, LGD, and EAD engines", "Multi-tenant IFRS 9 computation pipeline", "Deterministic SHA-256 audit trail on every output"]'::jsonb,
            'PLATFORM_SYSTEM',
            NOW(),
            NOW()
        )
        """
    )

    # ── impersonation_sessions ───────────────────────────────────────────────
    op.create_table(
        "impersonation_sessions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("platform_user_id", sa.String(26), nullable=False),
        sa.Column("target_tenant_id", sa.String(26), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index(
        "impersonation_platform_active_idx",
        "impersonation_sessions",
        ["platform_user_id", "is_active"],
    )
    op.create_index("impersonation_target_tenant_idx", "impersonation_sessions", ["target_tenant_id"])


def downgrade() -> None:
    op.drop_index("impersonation_target_tenant_idx", table_name="impersonation_sessions")
    op.drop_index("impersonation_platform_active_idx", table_name="impersonation_sessions")
    op.drop_table("impersonation_sessions")

    op.execute("DROP TRIGGER IF EXISTS engine_versions_updated_at ON engine_versions")
    op.drop_index("engine_versions_is_current_idx", table_name="engine_versions")
    op.drop_table("engine_versions")

    op.execute("DROP TRIGGER IF EXISTS notification_preferences_updated_at ON notification_preferences")
    op.drop_index("notification_preferences_user_id_idx", table_name="notification_preferences")
    op.drop_table("notification_preferences")

    op.drop_index("audit_tenant_id_idx", table_name="audit_logs")
    op.drop_column("audit_logs", "tenant_id")

    op.drop_column("tenants", "close_requested_by")
    op.drop_column("tenants", "close_requested_at")
    op.drop_column("tenants", "engine_version_pin")
    op.drop_column("tenants", "mrr_cents")
    op.drop_column("tenants", "region")

    op.drop_column("segments", "is_active")

    op.drop_column("users", "avatar_storage_path")
    op.drop_column("users", "title")
