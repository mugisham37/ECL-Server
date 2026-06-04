"""initial auth schema

Revision ID: 0001
Revises:
Create Date: 2026-06-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "users_email_active_idx",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        "CREATE TRIGGER users_updated_at BEFORE UPDATE ON users "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    op.create_table(
        "tenants",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False, server_default="trial"),
        sa.Column("status", sa.String(32), nullable=False, server_default="trial"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("reporting_cadence", sa.String(16), nullable=False, server_default="monthly"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "tenants_slug_active_idx",
        "tenants",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        "CREATE TRIGGER tenants_updated_at BEFORE UPDATE ON tenants "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("user_id", "tenant_id", name="memberships_unique"),
    )
    op.create_index("memberships_user_idx", "tenant_memberships", ["user_id"])
    op.create_index("memberships_tenant_idx", "tenant_memberships", ["tenant_id"])
    op.execute(
        "CREATE TRIGGER tenant_memberships_updated_at BEFORE UPDATE ON tenant_memberships "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("invited_by_user_id", sa.String(26), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.execute(
        "CREATE TRIGGER invitations_updated_at BEFORE UPDATE ON invitations "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), nullable=False),
        sa.Column("token_family_id", sa.String(26), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), nullable=False),
        sa.Column("refresh_token_id", sa.String(26), nullable=False),
        sa.Column("device_type", sa.String(16), nullable=False),
        sa.Column("device_name", sa.Text(), nullable=True),
        sa.Column("browser", sa.Text(), nullable=True),
        sa.Column("ip_address_hash", sa.String(64), nullable=False),
        sa.Column("country", sa.String(8), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "sessions",
        "refresh_tokens",
        "email_verification_tokens",
        "password_reset_tokens",
        "invitations",
        "tenant_memberships",
        "tenants",
        "users",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
