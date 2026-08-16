"""convert api_key and onboarding datetime columns to timestamptz

Revision ID: h0a1b2c3d4e5
Revises: g9c3d6f0e2a5
Create Date: 2026-08-17 00:00:00.000000

Fixes SWX-005: asyncpg raises DataError when inserting timezone-aware
datetime values (from utc_now()) into TIMESTAMP WITHOUT TIME ZONE columns.

Affected columns:
  - swx_api_key.expires_at
  - swx_api_key.last_used_at
  - swx_onboarding_step.completed_at
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "h0a1b2c3d4e5"
down_revision: str | None = "g9c3d6f0e2a5"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "swx_api_key", "expires_at",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        nullable=True,
        postgresql_using="expires_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "swx_api_key", "last_used_at",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        nullable=True,
        postgresql_using="last_used_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "swx_onboarding_step", "completed_at",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        nullable=True,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "swx_onboarding_step", "completed_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        existing_nullable=True,
        nullable=True,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "swx_api_key", "last_used_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        existing_nullable=True,
        nullable=True,
        postgresql_using="last_used_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "swx_api_key", "expires_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        existing_nullable=True,
        nullable=True,
        postgresql_using="expires_at AT TIME ZONE 'UTC'",
    )