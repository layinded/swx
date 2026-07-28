"""add multi currency tables

Revision ID: b7e1c2d3f4a5
Revises: c41b7a8e2f10
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7e1c2d3f4a5"
down_revision: str | None = "c41b7a8e2f10"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("swx_currency", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("code", sa.String(length=3), nullable=False), sa.Column("name", sa.String(length=100), nullable=False), sa.Column("symbol", sa.String(length=10), nullable=False), sa.Column("decimals", sa.Integer(), nullable=False, server_default="2"), sa.Column("is_base", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("status", sa.String(length=20), nullable=False, server_default="active"), sa.Column("minimum_amount", sa.Integer(), nullable=False, server_default="100"), sa.Column("supported_providers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_swx_currency_code"), "swx_currency", ["code"], unique=True)
    op.create_index("idx_swx_currency_status_base", "swx_currency", ["status", "is_base"], unique=False)
    op.create_table("swx_exchange_rate", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("base_currency", sa.String(length=3), nullable=False), sa.Column("quote_currency", sa.String(length=3), nullable=False), sa.Column("rate", sa.Float(), nullable=False), sa.Column("source", sa.String(length=50), nullable=True), sa.Column("fetched_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_swx_exchange_rate_base_currency"), "swx_exchange_rate", ["base_currency"], unique=False)
    op.create_index(op.f("ix_swx_exchange_rate_quote_currency"), "swx_exchange_rate", ["quote_currency"], unique=False)
    op.create_index("idx_swx_exchange_rate_pair_fetched", "swx_exchange_rate", ["base_currency", "quote_currency", "fetched_at"], unique=False)
    op.create_table("swx_wallet", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("currency", sa.String(length=3), nullable=False), sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_swx_wallet_account_id"), "swx_wallet", ["account_id"], unique=False)
    op.create_index("idx_swx_wallet_account_currency", "swx_wallet", ["account_id", "currency"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_swx_wallet_account_currency", table_name="swx_wallet")
    op.drop_index(op.f("ix_swx_wallet_account_id"), table_name="swx_wallet")
    op.drop_table("swx_wallet")
    op.drop_index("idx_swx_exchange_rate_pair_fetched", table_name="swx_exchange_rate")
    op.drop_index(op.f("ix_swx_exchange_rate_quote_currency"), table_name="swx_exchange_rate")
    op.drop_index(op.f("ix_swx_exchange_rate_base_currency"), table_name="swx_exchange_rate")
    op.drop_table("swx_exchange_rate")
    op.drop_index("idx_swx_currency_status_base", table_name="swx_currency")
    op.drop_index(op.f("ix_swx_currency_code"), table_name="swx_currency")
    op.drop_table("swx_currency")
