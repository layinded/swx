"""
Alembic Migration: v2.22.15 Add rotated_from_id to swx_api_key

Adds ``rotated_from_id`` nullable column to ``swx_api_key`` for key rotation
tracking. When an API key is rotated, the new key records which key it replaced.

Revision: v2_22_15_api_key_rotated_from
Replaces: None (standalone)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "v2_22_15_api_key_rotated_from"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "swx_api_key",
        sa.Column(
            "rotated_from_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("swx_api_key.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_swx_api_key_rotated_from_id",
        "swx_api_key",
        ["rotated_from_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_swx_api_key_rotated_from_id", table_name="swx_api_key")
    op.drop_column("swx_api_key", "rotated_from_id")