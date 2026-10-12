"""Alembic Migration: v2.22.18 Add session management columns to refresh token

Adds device_info, ip_address, and last_activity_at columns to
swx_refresh_token for SOC 2 CC6.1 session management.

Revision: v2_22_18_add_session_management_columns
Replaces: None (standalone)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_18_add_session_management_columns"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "swx_refresh_token",
        sa.Column("device_info", sa.String(255), nullable=True),
    )
    op.add_column(
        "swx_refresh_token",
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.add_column(
        "swx_refresh_token",
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("swx_refresh_token", "last_activity_at")
    op.drop_column("swx_refresh_token", "ip_address")
    op.drop_column("swx_refresh_token", "device_info")