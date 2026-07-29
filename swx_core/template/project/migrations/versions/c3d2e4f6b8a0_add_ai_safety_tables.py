"""add ai safety tables

Revision ID: c3d2e4f6b8a0
Revises: b2c1f3d5a7e9
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3d2e4f6b8a0"
down_revision: str | None = "b2c1f3d5a7e9"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_content_filter",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("filter_type", sa.String(length=50), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("action", sa.String(length=20), nullable=False, server_default=sa.text("'flag'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_content_filter_category"), "swx_content_filter", ["category"], unique=False)

    op.create_table(
        "swx_safety_check",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_preview", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filter_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("overall_verdict", sa.String(length=20), nullable=False, server_default=sa.text("'safe'")),
        sa.Column("action_taken", sa.String(length=20), nullable=False, server_default=sa.text("'none'")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["swx_conversation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_safety_check_user_id"), "swx_safety_check", ["user_id"], unique=False)
    op.create_index(op.f("ix_swx_safety_check_conversation_id"), "swx_safety_check", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_safety_check_conversation_id"), table_name="swx_safety_check")
    op.drop_index(op.f("ix_swx_safety_check_user_id"), table_name="swx_safety_check")
    op.drop_table("swx_safety_check")
    op.drop_index(op.f("ix_swx_content_filter_category"), table_name="swx_content_filter")
    op.drop_table("swx_content_filter")