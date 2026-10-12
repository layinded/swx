"""
Add tenant_id to users table for multi-tenant support

Revision ID: add_tenant_id_to_users
Revises: (your_last_migration)
Create Date: 2026-05-29

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head

"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "add_tenant_id_to_users"
down_revision: Union[str, None] = None  # UPDATE THIS to your current head
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tenant_id column (nullable first for existing data)
    op.add_column(
        "swx_users",
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            nullable=True,
        ),
    )
    
    # Create index for tenant filtering
    op.create_index(
        "ix_swx_users_tenant_id",
        "swx_users",
        ["tenant_id"],
    )
    
    # Add foreign key constraint (optional - requires swx_team table)
    # Uncomment if you have swx_team table:
    # op.create_foreign_key(
    #     "fk_swx_users_tenant_id",
    #     "swx_users",
    #     "swx_team",
    #     ["tenant_id"],
    #     ["id"],
    #     ondelete="SET NULL",
    # )
    
    # Optionally: Set default tenant for existing users
    # Replace YOUR_DEFAULT_TENANT_ID with actual UUID
    # op.execute(
    #     "UPDATE swx_users SET tenant_id = 'YOUR_DEFAULT_TENANT_ID' WHERE tenant_id IS NULL"
    # )
    
    # Uncomment to make tenant_id NOT NULL after setting defaults:
    # op.alter_column("swx_users", "tenant_id", nullable=False)


def downgrade() -> None:
    # Drop foreign key first (if created)
    # op.drop_constraint("fk_swx_users_tenant_id", "swx_users", type_="foreignkey")
    
    # Drop index
    op.drop_index("ix_swx_users_tenant_id", table_name="swx_users")
    
    # Drop column
    op.drop_column("swx_users", "tenant_id")


# =============================================================================
# MIGRATION STRATEGIES FOR EXISTING APPLICATIONS
# =============================================================================
#
# SCENARIO 1: Single-tenant application becoming multi-tenant
# ---------------------------------------------------------
# 1. Add tenant_id column (nullable)
# 2. Create a default tenant in swx_team table
# 3. Update existing users to point to default tenant
# 4. Make tenant_id NOT NULL
#
# Example:
#   # Step 1: Create default tenant
#   INSERT INTO swx_team (id, name, description)
#   VALUES ('uuid-here', 'Default', 'Default tenant for existing users');
#   
#   # Step 2: Update existing users
#   UPDATE swx_users SET tenant_id = 'uuid-here' WHERE tenant_id IS NULL;
#   
#   # Step 3: Make NOT NULL
#   ALTER TABLE swx_users ALTER COLUMN tenant_id SET NOT NULL;
#
#
# SCENARIO 2: New multi-tenant application
# ----------------------------------------
# 1. Add tenant_id column
# 2. Users are assigned tenant during registration
# 3. Keep nullable=True if you have global users (super-admins)
#
#
# SCENARIO 3: Existing multi-tenant with different field name
# ---------------------------------------------------------
# If your app uses org_id instead of tenant_id:
# 
# Option A: Change User model to use your field name
#   class UserBase(Base):
#       tenant_id: UUID = Field(sa_column_kwargs={"name": "org_id"})
#
# Option B: Create a database column alias in migration
#   op.add_column("swx_users", sa.Column("tenant_id", sa.Uuid(), nullable=True))
#   # tenant_id and org_id are the same column
#
#
# =============================================================================
# POST-MIGRATION STEPS
# =============================================================================
#
# 1. Update TenantAwareRepository to use your field name:
#    repository = TenantAwareRepository(model=Product, tenant_field="org_id")
#
# 2. Update TenantContextMiddleware to extract tenant correctly:
#    - From JWT claims
#    - From X-Tenant-ID header
#    - From user.organization_id
#
# 3. Ensure all new user registrations include tenant_id
#
# 4. Test tenant isolation:
#    - Users from tenant A cannot see tenant B's data
#    - Super-admins can see all data
#
# =============================================================================