"""add trial_ends_at to subscription + backfill from metadata

Revision ID: g9c3d6f0e2a5
Revises: f8b2d5e7a1c3
Create Date: 2026-08-11 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "g9c3d6f0e2a5"
down_revision: str | None = "f8b2d5e7a1c3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "swx_billing_subscription",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill: migrate existing trial_ends_at from JSON metadata to the new column.
    # Only touches rows where subscription_metadata->>'trial_ends_at' is non-null.
    op.execute("""
        UPDATE swx_billing_subscription
        SET trial_ends_at = (subscription_metadata ->> 'trial_ends_at')::timestamptz
        WHERE subscription_metadata ? 'trial_ends_at'
          AND trial_ends_at IS NULL;
    """)


def downgrade() -> None:
    # Preserve trial_ends_at back into JSON metadata before dropping the column.
    op.execute("""
        UPDATE swx_billing_subscription
        SET subscription_metadata = COALESCE(subscription_metadata, '{}'::jsonb)
            || jsonb_build_object('trial_ends_at', trial_ends_at::text)
        WHERE trial_ends_at IS NOT NULL;
    """)

    op.drop_column("swx_billing_subscription", "trial_ends_at")