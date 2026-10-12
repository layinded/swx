"""add user lockout and reset rate limit columns

Revision ID: a1b2c3d4e5f6
Revises: h0a1b2c3d4e5
Create Date: 2026-08-24 00:00:00.000000

SOC 2 CC6.1: Account lockout after failed logins and password reset rate limiting.
Adds failed_login_attempts, locked_until, and password_reset_requested_at to swx_users.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "h0a1b2c3d4e5"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "swx_users",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
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