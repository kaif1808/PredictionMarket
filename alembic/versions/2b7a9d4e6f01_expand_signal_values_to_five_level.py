"""expand signal values to five-level alphabet

Revision ID: 2b7a9d4e6f01
Revises: c4a1d9e8b6f2
Create Date: 2026-06-03 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "2b7a9d4e6f01"
down_revision = "c4a1d9e8b6f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("signals") as batch_op:
        batch_op.drop_constraint("ck_signal_value", type_="check")
        batch_op.alter_column(
            "signal_value",
            existing_type=sa.String(length=1),
            type_=sa.String(length=2),
            existing_nullable=False,
        )

    op.execute(
        """
        UPDATE signals
        SET signal_value = CASE
            WHEN signal_value = 'H' THEN 'S+'
            WHEN signal_value = 'L' THEN 'S-'
            ELSE signal_value
        END
        """
    )

    with op.batch_alter_table("signals") as batch_op:
        batch_op.create_check_constraint(
            "ck_signal_value",
            "signal_value IN ('S+','M+','N','M-','S-')",
        )


def downgrade() -> None:
    with op.batch_alter_table("signals") as batch_op:
        batch_op.drop_constraint("ck_signal_value", type_="check")

    op.execute(
        """
        UPDATE signals
        SET signal_value = CASE
            WHEN signal_value IN ('M-', 'S-') THEN 'L'
            ELSE 'H'
        END
        """
    )

    with op.batch_alter_table("signals") as batch_op:
        batch_op.alter_column(
            "signal_value",
            existing_type=sa.String(length=2),
            type_=sa.String(length=1),
            existing_nullable=False,
        )
        batch_op.create_check_constraint("ck_signal_value", "signal_value IN ('H','L')")
