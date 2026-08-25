"""Add social_accounts table for account linking

Revision ID: v2_22_12
Revises: v2_22_11
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa

revision = "v2_22_12"
down_revision = "v2_22_11_add_email_verified_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "swx_social_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("swx_users.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "provider_id", name="uq_social_accounts_provider_provider_id"),
    )


def downgrade() -> None:
    op.drop_table("swx_social_accounts")