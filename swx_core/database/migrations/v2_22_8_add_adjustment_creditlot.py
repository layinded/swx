"""
Alembic Migration: v2.22.8 Add Wallet Adjustment + Credit Lot Tables
=====================================================================

Creates ``swx_wallet_adjustment_request`` and ``swx_credit_lot`` tables.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_8_adjustment_creditlot"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_wallet_adjustment_request",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount_nano", sa.Integer, nullable=False),
        sa.Column("adjustment_type", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'proposed'"),
        sa.Column("proposed_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("swx_admin_user.id"), nullable=False),
        sa.Column("approved_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("swx_admin_user.id"), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "swx_credit_lot",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("tokens_total", sa.Integer, nullable=False),
        sa.Column("tokens_consumed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("swx_credit_lot")
    op.drop_table("swx_wallet_adjustment_request")