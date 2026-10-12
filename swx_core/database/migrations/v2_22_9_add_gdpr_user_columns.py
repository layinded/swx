"""
Alembic Migration: v2.22.9 Add GDPR User Columns
=================================================

Adds ``deactivated_at``, ``gdpr_deleted_at``, and ``anonymous`` columns
to ``swx_users``. Nullable-first with server defaults; backfills existing
rows where ``is_active`` is NULL to TRUE.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_9_gdpr_user_columns"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Add nullable columns first (no data loss)
    op.add_column("swx_users", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("swx_users", sa.Column("gdpr_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("swx_users", sa.Column("anonymous", sa.Boolean(), nullable=True, server_default=sa.text("false")))

    # Backfill: set is_active = TRUE where NULL (pre-existing rows)
    op.execute("UPDATE swx_users SET is_active = TRUE WHERE is_active IS NULL")

    # Backfill: set anonymous = FALSE where NULL (just in case)
    op.execute("UPDATE swx_users SET anonymous = FALSE WHERE anonymous IS NULL")

    # Now make anonymous NOT NULL with server default
    op.alter_column("swx_users", "anonymous", nullable=False, server_default=sa.text("false"))


def downgrade() -> None:
    op.drop_column("swx_users", "anonymous")
    op.drop_column("swx_users", "gdpr_deleted_at")
    op.drop_column("swx_users", "deactivated_at")