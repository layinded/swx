"""
Alembic Migration: Add swx_onboarding_step table
=================================================

Creates the ``swx_onboarding_step`` table for per-user onboarding
step tracking.  Each row records whether a registered step is pending,
completed, or skipped.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


revision: str = "v2_19_0_onboarding_step"
down_revision: str | None = None  # UPDATE THIS to your current head
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_onboarding_step",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", PG_UUID(as_uuid=True), sa.ForeignKey("swx_user.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "step_key", name="idx_swx_onboarding_step_user_key"),
    )


def downgrade() -> None:
    op.drop_table("swx_onboarding_step")