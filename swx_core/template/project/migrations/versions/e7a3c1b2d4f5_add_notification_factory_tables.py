"""add notification factory tables

Revision ID: e7a3c1b2d4f5
Revises: d1f6e4a9c3b2
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e7a3c1b2d4f5"
down_revision: str | None = "d1f6e4a9c3b2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("swx_email_provider_config", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("name", sa.String(length=50), nullable=False), sa.Column("provider_type", sa.String(length=30), nullable=False), sa.Column("host", sa.String(length=255), nullable=True), sa.Column("port", sa.Integer(), nullable=True), sa.Column("username", sa.String(length=255), nullable=True), sa.Column("password", sa.String(length=500), nullable=True), sa.Column("api_key", sa.String(length=500), nullable=True), sa.Column("from_email", sa.String(length=255), nullable=False), sa.Column("from_name", sa.String(length=100), nullable=True), sa.Column("is_ssl", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("priority", sa.Integer(), nullable=False, server_default="0"), sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"), sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"), sa.Column("extra_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("name"))
    op.create_index(op.f("ix_swx_email_provider_config_name"), "swx_email_provider_config", ["name"], unique=True)
    op.create_index(op.f("ix_swx_email_provider_config_provider_type"), "swx_email_provider_config", ["provider_type"], unique=False)
    op.create_table("swx_sms_provider_config", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("name", sa.String(length=50), nullable=False), sa.Column("provider_type", sa.String(length=30), nullable=False), sa.Column("account_sid", sa.String(length=255), nullable=True), sa.Column("auth_token", sa.String(length=500), nullable=True), sa.Column("api_key", sa.String(length=500), nullable=True), sa.Column("username", sa.String(length=255), nullable=True), sa.Column("from_number", sa.String(length=20), nullable=True), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("priority", sa.Integer(), nullable=False, server_default="0"), sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"), sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"), sa.Column("extra_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("name"))
    op.create_index(op.f("ix_swx_sms_provider_config_name"), "swx_sms_provider_config", ["name"], unique=True)
    op.create_index(op.f("ix_swx_sms_provider_config_provider_type"), "swx_sms_provider_config", ["provider_type"], unique=False)
    op.create_table("swx_notification_template", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("key", sa.String(length=100), nullable=False), sa.Column("channel", sa.String(length=20), nullable=False), sa.Column("subject_template", sa.String(length=500), nullable=True), sa.Column("body_template", sa.Text(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("key"))
    op.create_index(op.f("ix_swx_notification_template_key"), "swx_notification_template", ["key"], unique=True)
    op.create_index(op.f("ix_swx_notification_template_channel"), "swx_notification_template", ["channel"], unique=False)
    op.create_table("swx_notification_preference", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("quiet_hours_start", sa.String(length=5), nullable=True), sa.Column("quiet_hours_end", sa.String(length=5), nullable=True), sa.Column("digest_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("digest_frequency", sa.String(length=20), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id"))
    op.create_index(op.f("ix_swx_notification_preference_user_id"), "swx_notification_preference", ["user_id"], unique=True)
    op.create_table("swx_notification", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("channel", sa.String(length=20), nullable=False), sa.Column("notification_type", sa.String(length=50), nullable=False), sa.Column("subject", sa.String(length=500), nullable=True), sa.Column("body", sa.Text(), nullable=False), sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")), sa.Column("provider_config_id", postgresql.UUID(as_uuid=True), nullable=True), sa.Column("provider_name", sa.String(length=50), nullable=True), sa.Column("provider_response", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True), sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True), sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.ForeignKeyConstraint(["team_id"], ["swx_team.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_swx_notification_team_id", "swx_notification", ["team_id"], unique=False)
    op.create_index(op.f("ix_swx_notification_user_id"), "swx_notification", ["user_id"], unique=False)
    op.create_index(op.f("ix_swx_notification_channel"), "swx_notification", ["channel"], unique=False)
    op.create_index(op.f("ix_swx_notification_notification_type"), "swx_notification", ["notification_type"], unique=False)
    op.create_index(op.f("ix_swx_notification_status"), "swx_notification", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_notification_status"), table_name="swx_notification")
    op.drop_index(op.f("ix_swx_notification_notification_type"), table_name="swx_notification")
    op.drop_index(op.f("ix_swx_notification_channel"), table_name="swx_notification")
    op.drop_index("ix_swx_notification_team_id", table_name="swx_notification")
    op.drop_index(op.f("ix_swx_notification_user_id"), table_name="swx_notification")
    op.drop_table("swx_notification")
    op.drop_index(op.f("ix_swx_notification_preference_user_id"), table_name="swx_notification_preference")
    op.drop_table("swx_notification_preference")
    op.drop_index(op.f("ix_swx_notification_template_channel"), table_name="swx_notification_template")
    op.drop_index(op.f("ix_swx_notification_template_key"), table_name="swx_notification_template")
    op.drop_table("swx_notification_template")
    op.drop_index(op.f("ix_swx_sms_provider_config_provider_type"), table_name="swx_sms_provider_config")
    op.drop_index(op.f("ix_swx_sms_provider_config_name"), table_name="swx_sms_provider_config")
    op.drop_table("swx_sms_provider_config")
    op.drop_index(op.f("ix_swx_email_provider_config_provider_type"), table_name="swx_email_provider_config")
    op.drop_index(op.f("ix_swx_email_provider_config_name"), table_name="swx_email_provider_config")
    op.drop_table("swx_email_provider_config")
