"""add onboarding step table

Revision ID: e8c1f3d5a9b2
Revises: d5e2a1b3c7f8
Create Date: 2026-08-03 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e8c1f3d5a9b2"
down_revision: str | None = "d5e2a1b3c7f8"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_onboarding_step",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["swx_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_swx_onboarding_step_user_key", "swx_onboarding_step", ["user_id", "step_key"], unique=True)
    op.create_index(op.f("ix_swx_onboarding_step_step_key"), "swx_onboarding_step", ["step_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_onboarding_step_step_key"), table_name="swx_onboarding_step")
    op.drop_index("idx_swx_onboarding_step_user_key", table_name="swx_onboarding_step")
    op.drop_table("swx_onboarding_step")