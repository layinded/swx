"""add compliance audit tables

Revision ID: d1f6e4a9c3b2
Revises: cb96a87ddcc2
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d1f6e4a9c3b2"
down_revision: str | None = "cb96a87ddcc2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    _ = op.create_table(
        "swx_compliance_config",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_swx_compliance_config_category"), "swx_compliance_config", ["category"], unique=False)
    op.create_index(op.f("ix_swx_compliance_config_key"), "swx_compliance_config", ["key"], unique=True)

    _ = op.create_table(
        "swx_data_subject_request",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_token", sa.String(length=255), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("verification_token"),
    )
    op.create_index(op.f("ix_swx_data_subject_request_request_type"), "swx_data_subject_request", ["request_type"], unique=False)
    op.create_index(op.f("ix_swx_data_subject_request_status"), "swx_data_subject_request", ["status"], unique=False)
    op.create_index(op.f("ix_swx_data_subject_request_user_id"), "swx_data_subject_request", ["user_id"], unique=False)

    _ = op.create_table(
        "swx_retention_policy",
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("action_on_expiry", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_type"),
    )
    op.create_index(op.f("ix_swx_retention_policy_resource_type"), "swx_retention_policy", ["resource_type"], unique=True)

    op.add_column("swx_audit_log", sa.Column("severity", sa.String(length=20), nullable=True, server_default=sa.text("'info'")))
    op.add_column("swx_audit_log", sa.Column("data_classification", sa.String(length=50), nullable=True))
    op.add_column("swx_audit_log", sa.Column("access_result", sa.String(length=50), nullable=True))
    op.add_column("swx_audit_log", sa.Column("masked_ip", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_swx_audit_log_severity"), "swx_audit_log", ["severity"], unique=False)
    op.create_index(op.f("ix_swx_audit_log_data_classification"), "swx_audit_log", ["data_classification"], unique=False)
    op.create_index(op.f("ix_swx_audit_log_access_result"), "swx_audit_log", ["access_result"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_audit_log_access_result"), table_name="swx_audit_log")
    op.drop_index(op.f("ix_swx_audit_log_data_classification"), table_name="swx_audit_log")
    op.drop_index(op.f("ix_swx_audit_log_severity"), table_name="swx_audit_log")
    op.drop_column("swx_audit_log", "masked_ip")
    op.drop_column("swx_audit_log", "access_result")
    op.drop_column("swx_audit_log", "data_classification")
    op.drop_column("swx_audit_log", "severity")

    op.drop_index(op.f("ix_swx_retention_policy_resource_type"), table_name="swx_retention_policy")
    op.drop_table("swx_retention_policy")

    op.drop_index(op.f("ix_swx_data_subject_request_user_id"), table_name="swx_data_subject_request")
    op.drop_index(op.f("ix_swx_data_subject_request_status"), table_name="swx_data_subject_request")
    op.drop_index(op.f("ix_swx_data_subject_request_request_type"), table_name="swx_data_subject_request")
    op.drop_table("swx_data_subject_request")

    op.drop_index(op.f("ix_swx_compliance_config_key"), table_name="swx_compliance_config")
    op.drop_index(op.f("ix_swx_compliance_config_category"), table_name="swx_compliance_config")
    op.drop_table("swx_compliance_config")
