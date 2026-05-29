"""add practice market flag and market number constraint

Revision ID: 9d2f6b4a1c30
Revises: 7f1c2a9b4d55
Create Date: 2026-05-29 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9d2f6b4a1c30"
down_revision = "7f1c2a9b4d55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "markets",
        sa.Column("is_practice", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    with op.batch_alter_table("markets") as batch_op:
        batch_op.drop_constraint("ck_market_number", type_="check")
        batch_op.create_check_constraint(
            "ck_market_number",
            "(is_practice AND market_number = 0) OR ((NOT is_practice) AND market_number BETWEEN 1 AND 4)",
        )


def downgrade() -> None:
    with op.batch_alter_table("markets") as batch_op:
        batch_op.drop_constraint("ck_market_number", type_="check")
        batch_op.create_check_constraint("ck_market_number", "market_number BETWEEN 1 AND 4")
    op.drop_column("markets", "is_practice")
