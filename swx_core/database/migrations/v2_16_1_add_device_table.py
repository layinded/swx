"""
Alembic Migration: v2_16_1 Add Device Registration Table
========================================================

Creates the swx_device table for push notification token management.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "v2_16_1_add_device"
down_revision: Union[str, None] = None  # UPDATE THIS to your current head
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "swx_device",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False, server_default="ios"),
        sa.Column("fcm_token", sa.String(500), nullable=False),
        sa.Column("device_name", sa.String(200), nullable=True),
        sa.Column("device_model", sa.String(200), nullable=True),
        sa.Column("os_version", sa.String(50), nullable=True),
        sa.Column("app_version", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_data", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_swx_device_user_id", "swx_device", ["user_id"])
    op.create_index("ix_swx_device_platform", "swx_device", ["platform"])
    op.create_index("ix_swx_device_fcm_token", "swx_device", ["fcm_token"])
    op.create_index("ix_swx_device_status", "swx_device", ["status"])


def downgrade() -> None:
    op.drop_index("ix_swx_device_status", table_name="swx_device")
    op.drop_index("ix_swx_device_fcm_token", table_name="swx_device")
    op.drop_index("ix_swx_device_platform", table_name="swx_device")
    op.drop_index("ix_swx_device_user_id", table_name="swx_device")
    op.drop_table("swx_device")