"""add llm provider tables

Revision ID: c41b7a8e2f10
Revises: 9b2f6c1d4a7e
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c41b7a8e2f10"
down_revision: str | None = "9b2f6c1d4a7e"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_llm_provider_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("credentials", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("default_params", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supported_phases", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("cost_per_1k_tokens", sa.Float(), nullable=True),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supports_json_mode", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("max_retries", sa.Integer(), nullable=True),
        sa.Column("circuit_breaker_threshold", sa.Integer(), nullable=True),
        sa.Column("circuit_breaker_reset_seconds", sa.Integer(), nullable=True),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
        sa.Column("daily_token_limit", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["team_id"], ["swx_team.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_swx_llm_provider_config_team_id", "swx_llm_provider_config", ["team_id"], unique=False)
    op.create_index(op.f("ix_swx_llm_provider_config_provider"), "swx_llm_provider_config", ["provider"], unique=False)
    op.create_index("idx_swx_llm_provider_phase_priority", "swx_llm_provider_config", ["is_active", "priority"], unique=False)

    op.create_table(
        "swx_llm_usage_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_config_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("phase", sa.String(length=50), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["provider_config_id"], ["swx_llm_provider_config.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_llm_usage_log_account_id"), "swx_llm_usage_log", ["account_id"], unique=False)
    op.create_index("idx_swx_llm_usage_account_created", "swx_llm_usage_log", ["account_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_swx_llm_usage_account_created", table_name="swx_llm_usage_log")
    op.drop_index(op.f("ix_swx_llm_usage_log_account_id"), table_name="swx_llm_usage_log")
    op.drop_table("swx_llm_usage_log")
    op.drop_index("idx_swx_llm_provider_phase_priority", table_name="swx_llm_provider_config")
    op.drop_index("ix_swx_llm_provider_config_team_id", table_name="swx_llm_provider_config")
    op.drop_index(op.f("ix_swx_llm_provider_config_provider"), table_name="swx_llm_provider_config")
    op.drop_table("swx_llm_provider_config")
