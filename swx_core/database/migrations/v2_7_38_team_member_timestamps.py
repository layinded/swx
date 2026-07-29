"""
Alembic Migration: v2.7.38 Team Member Timestamps
==================================================

This migration adds timestamp columns to swx_team_member table:
  - created_at (timestamp, default now())
  - updated_at (timestamp, default now(), on update now())

These columns are required by the TeamMember model but were missing from
previous migrations.

New columns:
  - swx_team_member.created_at (timestamp, default now(), nullable=False)
  - swx_team_member.updated_at (timestamp, default now(), nullable=False)

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "v2_7_38_team_member_timestamps"
down_revision: Union[str, None] = None  # UPDATE THIS to your current head
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add created_at and updated_at columns to swx_team_member."""
    op.add_column(
        "swx_team_member",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "swx_team_member",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Remove created_at and updated_at columns from swx_team_member."""
    op.drop_column("swx_team_member", "updated_at")
    op.drop_column("swx_team_member", "created_at")