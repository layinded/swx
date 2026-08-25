"""
Alembic Migration: v2.22.6 Add Subscription Grace Period Fields
================================================================

Adds ``grace_period_ends_at`` and ``renewal_failure_count`` columns to the
``swx_billing_subscription`` table for renewal failure handling.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_6_sub_grace"
down_revision: str | None = None  # UPDATE THIS to your current head
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("swx_billing_subscription", sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("swx_billing_subscription", sa.Column("renewal_failure_count", sa.Integer, nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("swx_billing_subscription", "renewal_failure_count")
    op.drop_column("swx_billing_subscription", "grace_period_ends_at")