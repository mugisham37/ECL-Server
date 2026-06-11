"""add email_outbox table

Revision ID: 2eeb67246638
Revises: 0005
Create Date: 2026-06-11 10:55:04.871564

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2eeb67246638'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_outbox',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('task_name', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dispatch_attempts', sa.Integer(), nullable=False),
        sa.Column('last_dispatch_error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_email_outbox_status'), 'email_outbox', ['status'], unique=False)
    op.create_index('ix_email_outbox_status_created', 'email_outbox', ['status', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_email_outbox_status_created', table_name='email_outbox')
    op.drop_index(op.f('ix_email_outbox_status'), table_name='email_outbox')
    op.drop_table('email_outbox')
