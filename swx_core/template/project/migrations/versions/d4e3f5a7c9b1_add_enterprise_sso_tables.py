"""add enterprise sso tables

Revision ID: d4e3f5a7c9b1
Revises: c3d2e4f6b8a0
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e3f5a7c9b1"
down_revision: str | None = "c3d2e4f6b8a0"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "swx_sso_provider",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider_type", sa.String(length=20), nullable=False),
        sa.Column("client_id", sa.String(length=500), nullable=True),
        sa.Column("client_secret", sa.String(length=1000), nullable=True),
        sa.Column("authorization_url", sa.String(length=1000), nullable=True),
        sa.Column("token_url", sa.String(length=1000), nullable=True),
        sa.Column("userinfo_url", sa.String(length=1000), nullable=True),
        sa.Column("issuer_url", sa.String(length=1000), nullable=True),
        sa.Column("sso_url", sa.String(length=1000), nullable=True),
        sa.Column("slo_url", sa.String(length=1000), nullable=True),
        sa.Column("certificate", sa.String(length=5000), nullable=True),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("domain", sa.String(length=200), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_sso_provider_domain"), "swx_sso_provider", ["domain"], unique=False)

    op.create_table(
        "swx_sso_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idp_session_id", sa.String(length=500), nullable=True),
        sa.Column("idp_user_id", sa.String(length=500), nullable=True),
        sa.Column("idp_attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["swx_sso_provider.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_swx_sso_session_user_id"), "swx_sso_session", ["user_id"], unique=False)
    op.create_index(op.f("ix_swx_sso_session_provider_id"), "swx_sso_session", ["provider_id"], unique=False)
    op.create_index(op.f("ix_swx_sso_session_status"), "swx_sso_session", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_sso_session_status"), table_name="swx_sso_session")
    op.drop_index(op.f("ix_swx_sso_session_provider_id"), table_name="swx_sso_session")
    op.drop_index(op.f("ix_swx_sso_session_user_id"), table_name="swx_sso_session")
    op.drop_table("swx_sso_session")
    op.drop_index(op.f("ix_swx_sso_provider_domain"), table_name="swx_sso_provider")
    op.drop_table("swx_sso_provider")