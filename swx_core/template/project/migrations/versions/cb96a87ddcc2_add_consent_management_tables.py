"""add consent management tables

Revision ID: cb96a87ddcc2
Revises:
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "cb96a87ddcc2"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    _ = op.create_table(
        "swx_consent_type",
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_swx_consent_type_key"), "swx_consent_type", ["key"], unique=True)

    _ = op.create_table(
        "swx_consent_version",
        sa.Column("consent_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("document_url", sa.String(length=500), nullable=True),
        sa.Column("document_text", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_date", sa.DateTime(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["consent_type_id"], ["swx_consent_type.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_consent_version_consent_type_id"), "swx_consent_version", ["consent_type_id"], unique=False)
    op.create_index("idx_swx_consent_version_type_active", "swx_consent_version", ["consent_type_id", "is_active"], unique=False)

    _ = op.create_table(
        "swx_user_consent",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["consent_type_id"], ["swx_consent_type.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_user_consent_consent_type_id"), "swx_user_consent", ["consent_type_id"], unique=False)
    op.create_index(op.f("ix_swx_user_consent_user_id"), "swx_user_consent", ["user_id"], unique=False)
    op.create_index("idx_swx_user_consent_status", "swx_user_consent", ["status"], unique=False)
    op.create_index("idx_swx_user_consent_user_type", "swx_user_consent", ["user_id", "consent_type_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_swx_user_consent_user_type", table_name="swx_user_consent")
    op.drop_index("idx_swx_user_consent_status", table_name="swx_user_consent")
    op.drop_index(op.f("ix_swx_user_consent_user_id"), table_name="swx_user_consent")
    op.drop_index(op.f("ix_swx_user_consent_consent_type_id"), table_name="swx_user_consent")
    op.drop_table("swx_user_consent")

    op.drop_index("idx_swx_consent_version_type_active", table_name="swx_consent_version")
    op.drop_index(op.f("ix_swx_consent_version_consent_type_id"), table_name="swx_consent_version")
    op.drop_table("swx_consent_version")

    op.drop_index(op.f("ix_swx_consent_type_key"), table_name="swx_consent_type")
    op.drop_table("swx_consent_type")
