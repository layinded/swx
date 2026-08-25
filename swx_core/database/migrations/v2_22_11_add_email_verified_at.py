"""Add email_verified_at to swx_users

Revision ID: v2_22_11
Revises: v2_22_10
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa

revision = "v2_22_11"
down_revision = "v2_22_10_add_mfa_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "swx_users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("swx_users", "email_verified_at")