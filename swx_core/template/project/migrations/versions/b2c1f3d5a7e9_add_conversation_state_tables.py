"""add conversation state tables

Revision ID: b2c1f3d5a7e9
Revises: a91c4e2f7b6d
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b2c1f3d5a7e9"
down_revision: str | None = "a91c4e2f7b6d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("swx_conversation", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("title", sa.String(length=500), nullable=True), sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")), sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_swx_conversation_user_id"), "swx_conversation", ["user_id"], unique=False)
    op.create_index(op.f("ix_swx_conversation_status"), "swx_conversation", ["status"], unique=False)
    op.create_table("swx_conversation_message", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("role", sa.String(length=20), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("token_count", sa.Integer(), nullable=True), sa.Column("model", sa.String(length=100), nullable=True), sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True), sa.Column("parent_message_id", postgresql.UUID(as_uuid=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.ForeignKeyConstraint(["conversation_id"], ["swx_conversation.id"]), sa.ForeignKeyConstraint(["parent_message_id"], ["swx_conversation_message.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_swx_conversation_message_conversation_id"), "swx_conversation_message", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_conversation_message_conversation_id"), table_name="swx_conversation_message")
    op.drop_table("swx_conversation_message")
    op.drop_index(op.f("ix_swx_conversation_status"), table_name="swx_conversation")
    op.drop_index(op.f("ix_swx_conversation_user_id"), table_name="swx_conversation")
    op.drop_table("swx_conversation")