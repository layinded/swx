"""add organization tables

Revision ID: f38a4c8d9b12
Revises: cb96a87ddcc2
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f38a4c8d9b12"
down_revision: str | None = "cb96a87ddcc2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    _ = op.create_table(
        "swx_organization",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["swx_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_swx_organization_name"), "swx_organization", ["name"], unique=False)
    op.create_index(op.f("ix_swx_organization_owner_id"), "swx_organization", ["owner_id"], unique=False)
    op.create_index(op.f("ix_swx_organization_slug"), "swx_organization", ["slug"], unique=True)

    _ = op.create_table(
        "swx_organization_member",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["invited_by"], ["swx_users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["swx_organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["swx_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member_user_org"),
    )
    op.create_index(op.f("ix_swx_organization_member_organization_id"), "swx_organization_member", ["organization_id"], unique=False)
    op.create_index(op.f("ix_swx_organization_member_user_id"), "swx_organization_member", ["user_id"], unique=False)

    _ = op.create_table(
        "swx_organization_invitation",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inviter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invitee_email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["inviter_id"], ["swx_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["swx_organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_swx_organization_invitation_invitee_email"), "swx_organization_invitation", ["invitee_email"], unique=False)
    op.create_index(op.f("ix_swx_organization_invitation_inviter_id"), "swx_organization_invitation", ["inviter_id"], unique=False)
    op.create_index(op.f("ix_swx_organization_invitation_organization_id"), "swx_organization_invitation", ["organization_id"], unique=False)
    op.create_index(op.f("ix_swx_organization_invitation_token"), "swx_organization_invitation", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_swx_organization_invitation_token"), table_name="swx_organization_invitation")
    op.drop_index(op.f("ix_swx_organization_invitation_organization_id"), table_name="swx_organization_invitation")
    op.drop_index(op.f("ix_swx_organization_invitation_inviter_id"), table_name="swx_organization_invitation")
    op.drop_index(op.f("ix_swx_organization_invitation_invitee_email"), table_name="swx_organization_invitation")
    op.drop_table("swx_organization_invitation")
    op.drop_index(op.f("ix_swx_organization_member_user_id"), table_name="swx_organization_member")
    op.drop_index(op.f("ix_swx_organization_member_organization_id"), table_name="swx_organization_member")
    op.drop_table("swx_organization_member")
    op.drop_index(op.f("ix_swx_organization_slug"), table_name="swx_organization")
    op.drop_index(op.f("ix_swx_organization_owner_id"), table_name="swx_organization")
    op.drop_index(op.f("ix_swx_organization_name"), table_name="swx_organization")
    op.drop_table("swx_organization")
