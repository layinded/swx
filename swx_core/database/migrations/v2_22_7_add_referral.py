"""
Alembic Migration: v2.22.7 Add Referral Tables
================================================

Creates ``swx_referral_code`` and ``swx_referral_event`` tables.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_7_referral"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_referral_code",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("swx_users.id"), nullable=False, index=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("max_referrals", sa.Integer, nullable=False, server_default="100"),
        sa.Column("referral_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bonus_tokens", sa.Integer, nullable=False, server_default="10000"),
        sa.Column("referrer_bonus_tokens", sa.Integer, nullable=False, server_default="10000"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "swx_referral_event",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("referral_code_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("swx_referral_code.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("referred_user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("swx_users.id"), nullable=False, index=True),
        sa.Column("referrer_bonus_credited", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("referred_bonus_credited", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("swx_referral_event")
    op.drop_table("swx_referral_code")