"""
Alembic Migration: v2.7.22 Schema Changes
==========================================

This migration adds the schema changes introduced in v2.7.22:

1. FK ondelete clauses on all foreign keys (CASCADE, RESTRICT, SET NULL)
2. Team table: owner_id (FK to swx_users.id, SET NULL), created_at, updated_at
3. Plan table: billing_interval enum column
4. BillingInterval enum type

New columns:
  - swx_team.owner_id (UUID, nullable, FK to swx_users.id ON DELETE SET NULL)
  - swx_team.created_at (timestamp, default now())
  - swx_team.updated_at (timestamp, default now())
  - swx_plan.billing_interval (varchar(20), default 'monthly')

FK ondelete changes:
  - swx_user_role.user_id → swx_users.id ON DELETE CASCADE
  - swx_user_role.role_id → swx_role.id ON DELETE CASCADE
  - swx_user_role.team_id → swx_team.id ON DELETE RESTRICT
  - swx_team_member.team_id → swx_team.id ON DELETE CASCADE
  - swx_team_member.user_id → swx_users.id ON DELETE CASCADE
  - swx_team_member.role_id → swx_role.id ON DELETE CASCADE
  - swx_user.tenant_id → swx_team.id ON DELETE SET NULL
  - swx_role_permission.role_id → swx_role.id ON DELETE CASCADE
  - swx_role_permission.permission_id → swx_permission.id ON DELETE CASCADE
  - swx_billing_plan_entitlement.plan_id → swx_billing_plan.id ON DELETE CASCADE
  - swx_billing_plan_entitlement.feature_id → swx_billing_feature.id ON DELETE CASCADE
  - swx_billing_subscription.account_id → swx_billing_account.id ON DELETE CASCADE
  - swx_billing_subscription.plan_id → swx_billing_plan.id ON DELETE RESTRICT
  - swx_billing_usage_record.account_id → swx_billing_account.id ON DELETE CASCADE
  - swx_billing_usage_record.feature_id → swx_billing_feature.id ON DELETE RESTRICT
  - swx_billing_usage_record.subscription_id → swx_billing_subscription.id ON DELETE CASCADE
  - swx_system_config_history.config_id → swx_system_config.id ON DELETE CASCADE

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "v2_7_22_schema_changes"
down_revision: Union[str, None] = None  # UPDATE THIS to your current head
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New columns on swx_team ---
    op.add_column("swx_team", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.add_column("swx_team", sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.add_column("swx_team", sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_swx_team_owner_id", "swx_team", ["owner_id"])
    op.create_foreign_key(
        "fk_swx_team_owner_id",
        "swx_team", "swx_users",
        ["owner_id"], ["id"],
        ondelete="SET NULL",
    )

    # --- New column on swx_plan ---
    op.add_column(
        "swx_billing_plan",
        sa.Column("billing_interval", sa.String(20), server_default="monthly", nullable=False),
    )

    # --- FK ondelete changes ---
    # Each requires dropping the old FK constraint and creating a new one with ondelete.

    # swx_user_role
    _replace_fk("swx_user_role", "fk_swx_user_role_user_id_swx_users", "swx_users", ["user_id"], ["id"], "CASCADE")
    _replace_fk("swx_user_role", "fk_swx_user_role_role_id_swx_role", "swx_role", ["role_id"], ["id"], "CASCADE")
    _replace_fk("swx_user_role", "fk_swx_user_role_team_id_swx_team", "swx_team", ["team_id"], ["id"], "RESTRICT")

    # swx_team_member
    _replace_fk("swx_team_member", "fk_swx_team_member_team_id_swx_team", "swx_team", ["team_id"], ["id"], "CASCADE")
    _replace_fk("swx_team_member", "fk_swx_team_member_user_id_swx_users", "swx_users", ["user_id"], ["id"], "CASCADE")
    _replace_fk("swx_team_member", "fk_swx_team_member_role_id_swx_role", "swx_role", ["role_id"], ["id"], "CASCADE")

    # swx_users (tenant_id)
    _replace_fk("swx_users", "fk_swx_users_tenant_id_swx_team", "swx_team", ["tenant_id"], ["id"], "SET NULL")

    # swx_role_permission
    _replace_fk("swx_role_permission", "fk_swx_role_permission_role_id_swx_role", "swx_role", ["role_id"], ["id"], "CASCADE")
    _replace_fk("swx_role_permission", "fk_swx_role_permission_permission_id_swx_permission", "swx_permission", ["permission_id"], ["id"], "CASCADE")

    # swx_billing_plan_entitlement
    _replace_fk("swx_billing_plan_entitlement", "fk_swx_billing_plan_entitlement_plan_id_swx_billing_plan", "swx_billing_plan", ["plan_id"], ["id"], "CASCADE")
    _replace_fk("swx_billing_plan_entitlement", "fk_swx_billing_plan_entitlement_feature_id_swx_billing_feature", "swx_billing_feature", ["feature_id"], ["id"], "CASCADE")

    # swx_billing_subscription
    _replace_fk("swx_billing_subscription", "fk_swx_billing_subscription_account_id_swx_billing_account", "swx_billing_account", ["account_id"], ["id"], "CASCADE")
    _replace_fk("swx_billing_subscription", "fk_swx_billing_subscription_plan_id_swx_billing_plan", "swx_billing_plan", ["plan_id"], ["id"], "RESTRICT")

    # swx_billing_usage_record
    _replace_fk("swx_billing_usage_record", "fk_swx_billing_usage_record_account_id_swx_billing_account", "swx_billing_account", ["account_id"], ["id"], "CASCADE")
    _replace_fk("swx_billing_usage_record", "fk_swx_billing_usage_record_feature_id_swx_billing_feature", "swx_billing_feature", ["feature_id"], ["id"], "RESTRICT")
    _replace_fk("swx_billing_usage_record", "fk_swx_billing_usage_record_subscription_id_swx_billing_subscription", "swx_billing_subscription", ["subscription_id"], ["id"], "CASCADE")

    # swx_system_config_history
    _replace_fk("swx_system_config_history", "fk_swx_system_config_history_config_id_swx_system_config", "swx_system_config", ["config_id"], ["id"], "CASCADE")


def downgrade() -> None:
    # Reverse FK ondelete changes (recreate without ondelete)
    # Note: This restores the original FK constraints without ondelete clauses.

    _drop_fk("swx_user_role", "fk_swx_user_role_user_id_swx_users")
    _drop_fk("swx_user_role", "fk_swx_user_role_role_id_swx_role")
    _drop_fk("swx_user_role", "fk_swx_user_role_team_id_swx_team")
    _drop_fk("swx_team_member", "fk_swx_team_member_team_id_swx_team")
    _drop_fk("swx_team_member", "fk_swx_team_member_user_id_swx_users")
    _drop_fk("swx_team_member", "fk_swx_team_member_role_id_swx_role")
    _drop_fk("swx_users", "fk_swx_users_tenant_id_swx_team")
    _drop_fk("swx_role_permission", "fk_swx_role_permission_role_id_swx_role")
    _drop_fk("swx_role_permission", "fk_swx_role_permission_permission_id_swx_permission")
    _drop_fk("swx_billing_plan_entitlement", "fk_swx_billing_plan_entitlement_plan_id_swx_billing_plan")
    _drop_fk("swx_billing_plan_entitlement", "fk_swx_billing_plan_entitlement_feature_id_swx_billing_feature")
    _drop_fk("swx_billing_subscription", "fk_swx_billing_subscription_account_id_swx_billing_account")
    _drop_fk("swx_billing_subscription", "fk_swx_billing_subscription_plan_id_swx_billing_plan")
    _drop_fk("swx_billing_usage_record", "fk_swx_billing_usage_record_account_id_swx_billing_account")
    _drop_fk("swx_billing_usage_record", "fk_swx_billing_usage_record_feature_id_swx_billing_feature")
    _drop_fk("swx_billing_usage_record", "fk_swx_billing_usage_record_subscription_id_swx_billing_subscription")
    _drop_fk("swx_system_config_history", "fk_swx_system_config_history_config_id_swx_system_config")

    # Recreate FKs without ondelete
    op.create_foreign_key("fk_swx_user_role_user_id_swx_users", "swx_user_role", "swx_users", ["user_id"], ["id"])
    op.create_foreign_key("fk_swx_user_role_role_id_swx_role", "swx_user_role", "swx_role", ["role_id"], ["id"])
    op.create_foreign_key("fk_swx_user_role_team_id_swx_team", "swx_user_role", "swx_team", ["team_id"], ["id"])
    op.create_foreign_key("fk_swx_team_member_team_id_swx_team", "swx_team_member", "swx_team", ["team_id"], ["id"])
    op.create_foreign_key("fk_swx_team_member_user_id_swx_users", "swx_team_member", "swx_users", ["user_id"], ["id"])
    op.create_foreign_key("fk_swx_team_member_role_id_swx_role", "swx_team_member", "swx_role", ["role_id"], ["id"])
    op.create_foreign_key("fk_swx_users_tenant_id_swx_team", "swx_users", "swx_team", ["tenant_id"], ["id"])
    op.create_foreign_key("fk_swx_role_permission_role_id_swx_role", "swx_role_permission", "swx_role", ["role_id"], ["id"])
    op.create_foreign_key("fk_swx_role_permission_permission_id_swx_permission", "swx_role_permission", "swx_permission", ["permission_id"], ["id"])
    op.create_foreign_key("fk_swx_billing_plan_entitlement_plan_id_swx_billing_plan", "swx_billing_plan_entitlement", "swx_billing_plan", ["plan_id"], ["id"])
    op.create_foreign_key("fk_swx_billing_plan_entitlement_feature_id_swx_billing_feature", "swx_billing_plan_entitlement", "swx_billing_feature", ["feature_id"], ["id"])
    op.create_foreign_key("fk_swx_billing_subscription_account_id_swx_billing_account", "swx_billing_subscription", "swx_billing_account", ["account_id"], ["id"])
    op.create_foreign_key("fk_swx_billing_subscription_plan_id_swx_billing_plan", "swx_billing_subscription", "swx_billing_plan", ["plan_id"], ["id"])
    op.create_foreign_key("fk_swx_billing_usage_record_account_id_swx_billing_account", "swx_billing_usage_record", "swx_billing_account", ["account_id"], ["id"])
    op.create_foreign_key("fk_swx_billing_usage_record_feature_id_swx_billing_feature", "swx_billing_usage_record", "swx_billing_feature", ["feature_id"], ["id"])
    op.create_foreign_key("fk_swx_billing_usage_record_subscription_id_swx_billing_subscription", "swx_billing_usage_record", "swx_billing_subscription", ["subscription_id"], ["id"])
    op.create_foreign_key("fk_swx_system_config_history_config_id_swx_system_config", "swx_system_config_history", "swx_system_config", ["config_id"], ["id"])

    # Drop new columns
    op.drop_column("swx_billing_plan", "billing_interval")
    op.drop_constraint("fk_swx_team_owner_id", "swx_team", type_="foreignkey")
    op.drop_index("ix_swx_team_owner_id", table_name="swx_team")
    op.drop_column("swx_team", "updated_at")
    op.drop_column("swx_team", "created_at")
    op.drop_column("swx_team", "owner_id")


def _replace_fk(table: str, fk_name: str, target_table: str, columns: list, target_columns: list, ondelete: str) -> None:
    op.drop_constraint(fk_name, table, type_="foreignkey")
    op.create_foreign_key(fk_name, table, target_table, columns, target_columns, ondelete=ondelete)


def _drop_fk(table: str, fk_name: str) -> None:
    op.drop_constraint(fk_name, table, type_="foreignkey")