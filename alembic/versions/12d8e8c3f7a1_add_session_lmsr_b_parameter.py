"""add session-level lmsr liquidity

Revision ID: 12d8e8c3f7a1
Revises: 00058f3d1f5a
Create Date: 2026-05-28 09:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "12d8e8c3f7a1"
down_revision = "00058f3d1f5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "lmsr_b_parameter",
            sa.Numeric(precision=8, scale=4),
            nullable=False,
            server_default="36",
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "lmsr_b_parameter")
