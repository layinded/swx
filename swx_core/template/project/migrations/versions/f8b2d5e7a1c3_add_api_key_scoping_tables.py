"""add api key scoping tables

Revision ID: f8b2d5e7a1c3
Revises: e7a3c1b2d4f5
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f8b2d5e7a1c3"
down_revision: str | None = "e7a3c1b2d4f5"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_api_key",
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=8), nullable=False),
        sa.Column("hashed_key", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rate_limit_override", sa.Integer(), nullable=True),
        sa.Column("metadata_", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["team_id"], ["swx_team.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hashed_key"),
    )
    op.create_index("ix_swx_api_key_team_id", "swx_api_key", ["team_id"], unique=False)
    op.create_index(op.f("ix_swx_api_key_key_prefix"), "swx_api_key", ["key_prefix"], unique=False)
    op.create_index(op.f("ix_swx_api_key_hashed_key"), "swx_api_key", ["hashed_key"], unique=True)
    op.create_index(op.f("ix_swx_api_key_user_id"), "swx_api_key", ["user_id"], unique=False)

    op.create_table(
        "swx_api_key_scope",
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["api_key_id"], ["swx_api_key.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_api_key_scope_api_key_id"), "swx_api_key_scope", ["api_key_id"], unique=False)
    op.create_index(op.f("ix_swx_api_key_scope_resource"), "swx_api_key_scope", ["resource"], unique=False)
    op.create_index(op.f("ix_swx_api_key_scope_action"), "swx_api_key_scope", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_api_key_scope_action"), table_name="swx_api_key_scope")
    op.drop_index(op.f("ix_swx_api_key_scope_resource"), table_name="swx_api_key_scope")
    op.drop_index(op.f("ix_swx_api_key_scope_api_key_id"), table_name="swx_api_key_scope")
    op.drop_table("swx_api_key_scope")

    op.drop_index(op.f("ix_swx_api_key_user_id"), table_name="swx_api_key")
    op.drop_index(op.f("ix_swx_api_key_hashed_key"), table_name="swx_api_key")
    op.drop_index("ix_swx_api_key_team_id", table_name="swx_api_key")
    op.drop_index(op.f("ix_swx_api_key_key_prefix"), table_name="swx_api_key")
    op.drop_table("swx_api_key")
