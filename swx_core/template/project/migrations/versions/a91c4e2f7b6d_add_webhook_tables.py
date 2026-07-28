"""add webhook tables

Revision ID: a91c4e2f7b6d
Revises: f8b2d5e7a1c3
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a91c4e2f7b6d"
down_revision: str | None = "f8b2d5e7a1c3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("swx_webhook_endpoint", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("name", sa.String(length=100), nullable=False), sa.Column("url", sa.String(length=2000), nullable=False), sa.Column("secret", sa.String(length=500), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("event_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="3"), sa.Column("retry_delay_seconds", sa.Integer(), nullable=False, server_default="60"), sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_swx_webhook_endpoint_user_id"), "swx_webhook_endpoint", ["user_id"], unique=False)
    op.create_table("swx_webhook_delivery", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("event_type", sa.String(length=255), nullable=False), sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")), sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_attempt_at", sa.DateTime(), nullable=True), sa.Column("next_retry_at", sa.DateTime(), nullable=True), sa.Column("response_status_code", sa.Integer(), nullable=True), sa.Column("response_body", sa.Text(), nullable=True), sa.Column("error_message", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.ForeignKeyConstraint(["endpoint_id"], ["swx_webhook_endpoint.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_swx_webhook_delivery_endpoint_id"), "swx_webhook_delivery", ["endpoint_id"], unique=False)
    op.create_index(op.f("ix_swx_webhook_delivery_event_type"), "swx_webhook_delivery", ["event_type"], unique=False)
    op.create_index(op.f("ix_swx_webhook_delivery_status"), "swx_webhook_delivery", ["status"], unique=False)
    op.create_table("swx_webhook_event", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("event_type", sa.String(length=255), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.ForeignKeyConstraint(["endpoint_id"], ["swx_webhook_endpoint.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_swx_webhook_event_endpoint_id"), "swx_webhook_event", ["endpoint_id"], unique=False)
    op.create_index(op.f("ix_swx_webhook_event_event_type"), "swx_webhook_event", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_webhook_event_event_type"), table_name="swx_webhook_event")
    op.drop_index(op.f("ix_swx_webhook_event_endpoint_id"), table_name="swx_webhook_event")
    op.drop_table("swx_webhook_event")
    op.drop_index(op.f("ix_swx_webhook_delivery_status"), table_name="swx_webhook_delivery")
    op.drop_index(op.f("ix_swx_webhook_delivery_event_type"), table_name="swx_webhook_delivery")
    op.drop_index(op.f("ix_swx_webhook_delivery_endpoint_id"), table_name="swx_webhook_delivery")
    op.drop_table("swx_webhook_delivery")
    op.drop_index(op.f("ix_swx_webhook_endpoint_user_id"), table_name="swx_webhook_endpoint")
    op.drop_table("swx_webhook_endpoint")
