"""collapse roles to informed/uninformed

Revision ID: 3a5b0f2e9c11
Revises: 12d8e8c3f7a1
Create Date: 2026-05-28 15:50:00.000000
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "3a5b0f2e9c11"
down_revision = "12d8e8c3f7a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("market_roles") as batch_op:
        batch_op.drop_constraint("ck_role_tier", type_="check")
        batch_op.create_check_constraint(
            "ck_role_tier",
            "role_tier IN ('uninformed','semi_informed','insider','informed')",
        )

    op.execute(
        """
        UPDATE market_roles
        SET role_tier = CASE
            WHEN role_tier IN ('insider', 'semi_informed') THEN 'informed'
            ELSE role_tier
        END
        """
    )

    with op.batch_alter_table("market_roles") as batch_op:
        batch_op.drop_constraint("ck_role_tier", type_="check")
        batch_op.create_check_constraint(
            "ck_role_tier",
            "role_tier IN ('uninformed','informed')",
        )


def downgrade() -> None:
    op.execute(
        """
        UPDATE market_roles
        SET role_tier = CASE
            WHEN role_tier = 'informed' THEN 'insider'
            ELSE role_tier
        END
        """
    )

    with op.batch_alter_table("market_roles") as batch_op:
        batch_op.drop_constraint("ck_role_tier", type_="check")
        batch_op.create_check_constraint(
            "ck_role_tier",
            "role_tier IN ('uninformed','semi_informed','insider')",
        )
