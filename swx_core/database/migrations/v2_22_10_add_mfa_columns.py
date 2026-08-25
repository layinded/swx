"""
Alembic Migration: v2.22.10 Add MFA Columns and Recovery Codes Table
====================================================================

Adds ``mfa_enabled``, ``mfa_secret``, and ``mfa_verified_at`` columns
to ``swx_users`` and creates ``swx_mfa_recovery_codes`` table.

Nullable-first with server defaults for boolean; backfills existing rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_10_mfa_columns"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("swx_users", sa.Column("mfa_enabled", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("swx_users", sa.Column("mfa_secret", sa.String(500), nullable=True))
    op.add_column("swx_users", sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE swx_users SET mfa_enabled = FALSE WHERE mfa_enabled IS NULL")

    op.alter_column("swx_users", "mfa_enabled", nullable=False, server_default=sa.text("false"))

    op.create_table(
        "swx_mfa_recovery_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("swx_users.id"), nullable=False, index=True),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("swx_mfa_recovery_codes")
    op.drop_column("swx_users", "mfa_verified_at")
    op.drop_column("swx_users", "mfa_secret")
    op.drop_column("swx_users", "mfa_enabled")