"""add onboarding columns to tenants

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("onboarding_progress", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "onboarding_progress")
    op.drop_column("tenants", "onboarding_completed_at")
