"""add session treated_count

Revision ID: c4a1d9e8b6f2
Revises: 9d2f6b4a1c30
Create Date: 2026-05-29 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c4a1d9e8b6f2"
down_revision = "9d2f6b4a1c30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("treated_count", sa.Integer(), nullable=False, server_default="3"),
    )


def downgrade() -> None:
    op.drop_column("sessions", "treated_count")
