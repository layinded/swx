"""add feature flags ab testing tables

Revision ID: f7b6d8e0a2c4
Revises: f6a5b7c9e1d3
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f7b6d8e0a2c4"
down_revision: str | None = "f6a5b7c9e1d3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_feature_flag",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("variants", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sticky", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_feature_flag_key"), "swx_feature_flag", ["key"], unique=True)

    op.create_table(
        "swx_flag_evaluation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("variant", sa.String(length=100), nullable=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.String(length=50), nullable=False, server_default=sa.text("'default'")),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["flag_id"], ["swx_feature_flag.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_flag_evaluation_flag_id"), "swx_flag_evaluation", ["flag_id"], unique=False)
    op.create_index(op.f("ix_swx_flag_evaluation_user_id"), "swx_flag_evaluation", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_flag_evaluation_user_id"), table_name="swx_flag_evaluation")
    op.drop_index(op.f("ix_swx_flag_evaluation_flag_id"), table_name="swx_flag_evaluation")
    op.drop_table("swx_flag_evaluation")
    op.drop_index(op.f("ix_swx_feature_flag_key"), table_name="swx_feature_flag")
    op.drop_table("swx_feature_flag")