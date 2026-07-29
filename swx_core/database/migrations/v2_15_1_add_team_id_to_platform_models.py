"""
Alembic Migration: v2.15.1 Add team_id to platform models
===========================================================

Adds optional team_id support to swx_llm_provider_config, swx_notification,
and swx_api_key so existing databases can use team-scoped records alongside
platform-level records.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Run: alembic upgrade head
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "v2_15_1_add_team_id"
down_revision: str | None = "v2_15_0_timestamptz"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("swx_llm_provider_config", sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(None, "swx_llm_provider_config", "swx_team", ["team_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_swx_llm_provider_config_team_id", "swx_llm_provider_config", ["team_id"], unique=False)

    op.add_column("swx_notification", sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(None, "swx_notification", "swx_team", ["team_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_swx_notification_team_id", "swx_notification", ["team_id"], unique=False)

    op.add_column("swx_api_key", sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(None, "swx_api_key", "swx_team", ["team_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_swx_api_key_team_id", "swx_api_key", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_swx_api_key_team_id", table_name="swx_api_key")
    op.drop_column("swx_api_key", "team_id")

    op.drop_index("ix_swx_notification_team_id", table_name="swx_notification")
    op.drop_column("swx_notification", "team_id")

    op.drop_index("ix_swx_llm_provider_config_team_id", table_name="swx_llm_provider_config")
    op.drop_column("swx_llm_provider_config", "team_id")
