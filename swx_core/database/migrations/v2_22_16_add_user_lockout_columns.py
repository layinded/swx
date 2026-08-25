"""
Alembic Migration: v2.22.16 Add user lockout columns

Adds ``failed_login_attempts``, ``locked_until``, and
``password_reset_requested_at`` to ``swx_users`` for SOC 2 CC6.1
account lockout and password reset rate limiting.

Revision: v2_22_16_add_user_lockout_columns
Replaces: None (standalone)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_16_add_user_lockout_columns"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "swx_users",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "swx_users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "swx_users",
        sa.Column("password_reset_requested_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("swx_users", "password_reset_requested_at")
    op.drop_column("swx_users", "locked_until")
    op.drop_column("swx_users", "failed_login_attempts")