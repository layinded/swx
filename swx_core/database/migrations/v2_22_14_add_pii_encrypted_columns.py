"""
Alembic Migration: v2.22.14 Add encrypted PII columns to swx_users

Adds ``email_encrypted`` and ``full_name_encrypted`` nullable columns for
dual-write PII encryption.  During migration both plaintext and encrypted
columns coexist; the plaintext columns will be dropped in a future major
version once all data is backfilled.

Revision: v2_22_14_pii_encrypted_columns
Replaces: None (standalone)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_14_pii_encrypted_columns"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "swx_users",
        sa.Column("email_encrypted", sa.String(1024), nullable=True),
    )
    op.add_column(
        "swx_users",
        sa.Column("full_name_encrypted", sa.String(1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("swx_users", "full_name_encrypted")
    op.drop_column("swx_users", "email_encrypted")