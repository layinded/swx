"""
Alembic Migration: v2_16_3 Add Email Provider + Notification Preference Fields
==============================================================================

Adds cost tracking, rate limits, country routing, and tracking fields to
swx_email_provider_config. Adds escalation and reminder fields to
swx_notification_preference.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "v2_16_3_add_notification_fields"
down_revision: Union[str, None] = None  # UPDATE THIS to your current head
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # swx_email_provider_config: cost/limits/country routing + tracking
    op.add_column("swx_email_provider_config", sa.Column("cost_per_email", sa.Float(), nullable=True))
    op.add_column("swx_email_provider_config", sa.Column("daily_limit", sa.Integer(), nullable=True))
    op.add_column("swx_email_provider_config", sa.Column("monthly_limit", sa.Integer(), nullable=True))
    op.add_column("swx_email_provider_config", sa.Column("rate_limit_per_hour", sa.Integer(), nullable=True))
    op.add_column("swx_email_provider_config", sa.Column("supported_countries", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("swx_email_provider_config", sa.Column("tracking_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")))
    op.add_column("swx_email_provider_config", sa.Column("open_tracking", sa.Boolean, nullable=False, server_default=sa.text("true")))
    op.add_column("swx_email_provider_config", sa.Column("click_tracking", sa.Boolean, nullable=False, server_default=sa.text("true")))
    op.add_column("swx_email_provider_config", sa.Column("reply_to", sa.String(255), nullable=True))

    # swx_notification_preference: escalation + reminder fields
    op.add_column("swx_notification_preference", sa.Column("reminder_time", sa.String(5), nullable=True))
    op.add_column("swx_notification_preference", sa.Column("escalation_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("swx_notification_preference", sa.Column("escalation_hours", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("swx_notification_preference", "escalation_hours")
    op.drop_column("swx_notification_preference", "escalation_enabled")
    op.drop_column("swx_notification_preference", "reminder_time")

    op.drop_column("swx_email_provider_config", "reply_to")
    op.drop_column("swx_email_provider_config", "click_tracking")
    op.drop_column("swx_email_provider_config", "open_tracking")
    op.drop_column("swx_email_provider_config", "tracking_enabled")
    op.drop_column("swx_email_provider_config", "supported_countries")
    op.drop_column("swx_email_provider_config", "rate_limit_per_hour")
    op.drop_column("swx_email_provider_config", "monthly_limit")
    op.drop_column("swx_email_provider_config", "daily_limit")
    op.drop_column("swx_email_provider_config", "cost_per_email")