"""
Migration: Add composite unique constraint to TeamMember

Bug #23: Users could be added to the same team multiple times.
This migration adds a unique constraint on (team_id, user_id).

Run with: alembic upgrade head
"""

from alembic import op


revision = "v2_7_24_team_member_unique"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_team_member_user_team",
        "swx_team_member",
        ["team_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_team_member_user_team",
        "swx_team_member",
        type_="unique",
    )