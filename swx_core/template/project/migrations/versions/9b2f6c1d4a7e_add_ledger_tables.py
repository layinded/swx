"""add ledger tables

Revision ID: 9b2f6c1d4a7e
Revises: f38a4c8d9b12
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9b2f6c1d4a7e"
down_revision: str | None = "f38a4c8d9b12"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_ledger_entry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["swx_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_ledger_entry_account_id"), "swx_ledger_entry", ["account_id"], unique=False)
    op.create_index(op.f("ix_swx_ledger_entry_idempotency_key"), "swx_ledger_entry", ["idempotency_key"], unique=False)
    op.create_index("idx_swx_ledger_entry_account_created", "swx_ledger_entry", ["account_id", "created_at"], unique=False)

    op.create_table(
        "swx_ledger_balance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("balance", sa.BigInteger(), nullable=False),
        sa.Column("last_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["last_entry_id"], ["swx_ledger_entry.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
    )
    op.create_index(op.f("ix_swx_ledger_balance_account_id"), "swx_ledger_balance", ["account_id"], unique=True)

    op.create_table(
        "swx_idempotency_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["entry_id"], ["swx_ledger_entry.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_swx_idempotency_record_account_id"), "swx_idempotency_record", ["account_id"], unique=False)
    op.create_index(op.f("ix_swx_idempotency_record_key"), "swx_idempotency_record", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_idempotency_record_key"), table_name="swx_idempotency_record")
    op.drop_index(op.f("ix_swx_idempotency_record_account_id"), table_name="swx_idempotency_record")
    op.drop_table("swx_idempotency_record")
    op.drop_index(op.f("ix_swx_ledger_balance_account_id"), table_name="swx_ledger_balance")
    op.drop_table("swx_ledger_balance")
    op.drop_index("idx_swx_ledger_entry_account_created", table_name="swx_ledger_entry")
    op.drop_index(op.f("ix_swx_ledger_entry_idempotency_key"), table_name="swx_ledger_entry")
    op.drop_index(op.f("ix_swx_ledger_entry_account_id"), table_name="swx_ledger_entry")
    op.drop_table("swx_ledger_entry")
