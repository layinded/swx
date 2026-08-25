"""
Alembic Migration: v2.22.5 Add Inbound Webhook Delivery Table
==============================================================

Creates the ``swx_inbound_webhook_delivery`` table for durable webhook
idempotency tracking across payment providers (Paystack, Flutterwave, Stripe).

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_22_5_inbound_webhook"
down_revision: str | None = None  # UPDATE THIS to your current head
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_inbound_webhook_delivery",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.String(20), nullable=False, index=True),
        sa.Column("event_id", sa.String(255), nullable=False, index=True),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "event_id", name="uq_swx_inbound_webhook_provider_event"),
    )
    op.create_index("idx_swx_inbound_webhook_provider_event", "swx_inbound_webhook_delivery", ["provider", "event_id"])
    op.create_index("idx_swx_inbound_webhook_created", "swx_inbound_webhook_delivery", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_swx_inbound_webhook_created", table_name="swx_inbound_webhook_delivery")
    op.drop_index("idx_swx_inbound_webhook_provider_event", table_name="swx_inbound_webhook_delivery")
    op.drop_table("swx_inbound_webhook_delivery")