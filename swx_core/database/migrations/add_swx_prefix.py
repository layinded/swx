"""
Alembic Migration: Add swx_ Prefix to Framework Tables
======================================================

This migration renames all swx_core framework tables to include the "swx_" prefix,
differentiating framework tables from user-defined tables.

Run this migration with:
    alembic upgrade head

Or manually apply to existing database:
    python -m swx_core.database.migrations.add_swx_prefix

Table Renames (21 tables):
- users → swx_users
- admin_user → swx_admin_user
- role → swx_role
- permission → swx_permission
- team → swx_team
- user_role → swx_user_role
- team_member → swx_team_member
- role_permission → swx_role_permission
- audit_log → swx_audit_log
- job → swx_job
- language → swx_language
- refresh_token → swx_refresh_token
- policy → swx_policy
- system_config → swx_system_config
- system_config_history → swx_system_config_history
- billing_account → swx_billing_account
- billing_feature → swx_billing_feature
- billing_plan → swx_billing_plan
- billing_plan_entitlement → swx_billing_plan_entitlement
- billing_subscription → swx_billing_subscription
- billing_usage_record → swx_billing_usage_record
"""

from alembic import op
import sqlalchemy as sa

revision = "v2.4.0_add_swx_prefix"
down_revision = None
branch_labels = None
depends_on = None

TABLE_RENAMES = [
    ("users", "swx_users"),
    ("admin_user", "swx_admin_user"),
    ("role", "swx_role"),
    ("permission", "swx_permission"),
    ("team", "swx_team"),
    ("user_role", "swx_user_role"),
    ("team_member", "swx_team_member"),
    ("role_permission", "swx_role_permission"),
    ("audit_log", "swx_audit_log"),
    ("job", "swx_job"),
    ("language", "swx_language"),
    ("refresh_token", "swx_refresh_token"),
    ("policy", "swx_policy"),
    ("system_config", "swx_system_config"),
    ("system_config_history", "swx_system_config_history"),
    ("billing_account", "swx_billing_account"),
    ("billing_feature", "swx_billing_feature"),
    ("billing_plan", "swx_billing_plan"),
    ("billing_plan_entitlement", "swx_billing_plan_entitlement"),
    ("billing_subscription", "swx_billing_subscription"),
    ("billing_usage_record", "swx_billing_usage_record"),
]

FOREIGN_KEY_UPDATES = {
    "swx_user_role": [
        ("user_id", "users", "swx_users"),
        ("role_id", "role", "swx_role"),
        ("team_id", "team", "swx_team"),
    ],
    "swx_team_member": [
        ("team_id", "team", "swx_team"),
        ("user_id", "users", "swx_users"),
        ("role_id", "role", "swx_role"),
    ],
    "swx_role_permission": [
        ("role_id", "role", "swx_role"),
        ("permission_id", "permission", "swx_permission"),
    ],
    "swx_system_config_history": [
        ("config_id", "system_config", "swx_system_config"),
    ],
    "swx_billing_plan_entitlement": [
        ("plan_id", "billing_plan", "swx_billing_plan"),
        ("feature_id", "billing_feature", "swx_billing_feature"),
    ],
    "swx_billing_subscription": [
        ("account_id", "billing_account", "swx_billing_account"),
        ("plan_id", "billing_plan", "swx_billing_plan"),
    ],
    "swx_billing_usage_record": [
        ("account_id", "billing_account", "swx_billing_account"),
        ("feature_id", "billing_feature", "swx_billing_feature"),
        ("subscription_id", "billing_subscription", "swx_billing_subscription"),
    ],
}


def upgrade() -> None:
    """Rename all framework tables with swx_ prefix."""
    conn = op.get_bind()
    
    for old_name, new_name in TABLE_RENAMES:
        if conn.dialect.has_table(conn, old_name):
            op.rename_table(old_name, new_name)
    
    for table_name, fk_updates in FOREIGN_KEY_UPDATES.items():
        if conn.dialect.has_table(conn, table_name):
            for column_name, old_ref_table, new_ref_table in fk_updates:
                try:
                    op.drop_constraint(
                        f"{table_name}_{column_name}_fkey",
                        table_name,
                        type_="foreignkey"
                    )
                except Exception:
                    pass
                try:
                    op.create_foreign_key(
                        f"{table_name}_{column_name}_fkey",
                        table_name,
                        new_ref_table,
                        [column_name],
                        ["id"]
                    )
                except Exception:
                    pass


def downgrade() -> None:
    """Remove swx_ prefix from all framework tables."""
    conn = op.get_bind()
    
    for old_name, new_name in reversed(TABLE_RENAMES):
        if conn.dialect.has_table(conn, new_name):
            op.rename_table(new_name, old_name)
    
    for table_name, fk_updates in reversed(list(FOREIGN_KEY_UPDATES.items())):
        new_table_name = table_name
        old_table_name = table_name.replace("swx_", "")
        
        if conn.dialect.has_table(conn, new_table_name):
            for column_name, old_ref_table, new_ref_table in fk_updates:
                try:
                    op.drop_constraint(
                        f"{new_table_name}_{column_name}_fkey",
                        new_table_name,
                        type_="foreignkey"
                    )
                except Exception:
                    pass
                try:
                    op.create_foreign_key(
                        f"{old_table_name}_{column_name}_fkey",
                        new_table_name,
                        old_ref_table,
                        [column_name],
                        ["id"]
                    )
                except Exception:
                    pass


if __name__ == "__main__":
    import sys
    print("Run this migration via: alembic upgrade head")
    print("Or generate a proper alembic revision with: alembic revision -m 'add_swx_prefix'")
    sys.exit(0)