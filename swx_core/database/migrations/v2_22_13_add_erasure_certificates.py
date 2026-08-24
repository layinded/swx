"""Add erasure certificates table for GDPR right-to-erasure compliance

Revision ID: v2_22_13
Revises: v2_22_12
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa

revision = "v2_22_13"
down_revision = "v2_22_12_add_social_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "swx_erasure_certificates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("swx_users.id"), nullable=False, index=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("swx_data_subject_request.id"), nullable=True),
        sa.Column("erasure_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("tables_affected", sa.Text, nullable=True),
        sa.Column("certificate_data", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("swx_erasure_certificates")