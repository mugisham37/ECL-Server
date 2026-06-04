"""segments, collateral types, audit logs, token blacklist, totp columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── segments ─────────────────────────────────────────────────────────────
    op.create_table(
        "segments",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("segments_tenant_idx", "segments", ["tenant_id"])
    op.create_index(
        "segments_tenant_name_unique_idx",
        "segments",
        ["tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        "CREATE TRIGGER segments_updated_at BEFORE UPDATE ON segments "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ── collateral_types ─────────────────────────────────────────────────────
    op.create_table(
        "collateral_types",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("haircut", sa.Numeric(5, 2), nullable=False),
        sa.Column("time_to_realize", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("collateral_types_tenant_idx", "collateral_types", ["tenant_id"])
    op.create_index(
        "collateral_types_tenant_name_unique_idx",
        "collateral_types",
        ["tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        "CREATE TRIGGER collateral_types_updated_at BEFORE UPDATE ON collateral_types "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("ip_address_hash", sa.String(64), nullable=True),
        sa.Column("user_agent_hash", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("audit_user_idx", "audit_logs", ["user_id"])
    op.create_index("audit_event_type_idx", "audit_logs", ["event_type"])
    op.create_index("audit_created_at_idx", "audit_logs", ["created_at"])
    op.create_index(
        "audit_user_event_time_idx",
        "audit_logs",
        ["user_id", "event_type", "created_at"],
    )

    # ── token_blacklist ───────────────────────────────────────────────────────
    op.create_table(
        "token_blacklist",
        sa.Column("jti", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("token_blacklist_user_idx", "token_blacklist", ["user_id"])
    op.create_index("token_blacklist_expires_idx", "token_blacklist", ["expires_at"])

    # ── users: TOTP columns ───────────────────────────────────────────────────
    op.add_column("users", sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("users", sa.Column("totp_backup_codes", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "totp_backup_codes")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret_encrypted")

    for table in ("token_blacklist", "audit_logs", "collateral_types", "segments"):
        op.drop_table(table)
