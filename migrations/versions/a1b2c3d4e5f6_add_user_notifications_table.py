"""add user_notifications table

Revision ID: a1b2c3d4e5f6
Revises: 2eeb67246638
Create Date: 2026-06-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "2eeb67246638"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_notifications",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("tenant_id", sa.String(length=26), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_notifications_user_id"), "user_notifications", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_notifications_tenant_id"), "user_notifications", ["tenant_id"], unique=False)
    op.create_index(
        "ix_user_notifications_user_created",
        "user_notifications",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_notifications_user_created", table_name="user_notifications")
    op.drop_index(op.f("ix_user_notifications_tenant_id"), table_name="user_notifications")
    op.drop_index(op.f("ix_user_notifications_user_id"), table_name="user_notifications")
    op.drop_table("user_notifications")
