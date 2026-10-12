"""
Alembic Migration: v2.22.17 Add log_hash to audit log

Adds ``log_hash`` column to ``swx_audit_log`` for SOC 2 CC7.2
tamper-evident hash chain verification. Each entry's hash is
SHA-256(previous_hash + canonical_entry_fields).

Revision: v2_22_17_add_audit_log_hash_chain
Replaces: None (standalone)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_17_add_audit_log_hash_chain"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "swx_audit_log",
        sa.Column("log_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_swx_audit_log_log_hash",
        "swx_audit_log",
        ["log_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_swx_audit_log_log_hash", table_name="swx_audit_log")
    op.drop_column("swx_audit_log", "log_hash")