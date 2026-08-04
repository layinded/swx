"""add credential_source and encrypted_api_key to llm provider config

Revision ID: d5e2a1b3c7f8
Revises: f8b2d5e7a1c3
Create Date: 2026-08-03 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d5e2a1b3c7f8"
down_revision: str | None = "f8b2d5e7a1c3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "swx_llm_provider_config",
        sa.Column("credential_source", sa.String(length=20), nullable=False, server_default=sa.text("'env_placeholder'")),
    )
    op.add_column(
        "swx_llm_provider_config",
        sa.Column("encrypted_api_key", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("swx_llm_provider_config", "encrypted_api_key")
    op.drop_column("swx_llm_provider_config", "credential_source")