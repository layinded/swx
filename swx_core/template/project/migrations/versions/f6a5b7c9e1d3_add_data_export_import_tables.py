"""add data export import tables

Revision ID: f6a5b7c9e1d3
Revises: e5f4a6b8d0c2
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a5b7c9e1d3"
down_revision: str | None = "e5f4a6b8d0c2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_data_export",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("export_type", sa.String(length=50), nullable=False, server_default=sa.text("'full'")),
        sa.Column("format", sa.String(length=20), nullable=False, server_default=sa.text("'json'")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_data_export_user_id"), "swx_data_export", ["user_id"], unique=False)

    op.create_table(
        "swx_data_import",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_type", sa.String(length=50), nullable=False, server_default=sa.text("'full'")),
        sa.Column("format", sa.String(length=20), nullable=False, server_default=sa.text("'json'")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("records_succeeded", sa.Integer(), nullable=True),
        sa.Column("records_failed", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_data_import_user_id"), "swx_data_import", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_data_import_user_id"), table_name="swx_data_import")
    op.drop_table("swx_data_import")
    op.drop_index(op.f("ix_swx_data_export_user_id"), table_name="swx_data_export")
    op.drop_table("swx_data_export")