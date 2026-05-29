"""add session-level tournament payout screen flag

Revision ID: 7f1c2a9b4d55
Revises: 3a5b0f2e9c11
Create Date: 2026-05-29 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f1c2a9b4d55"
down_revision = "3a5b0f2e9c11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "show_tournament_payout_screen",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "show_tournament_payout_screen")
