"""
Migration: Bug 25 + Bug 26 - Team roles and invitations

Bug #25: Separate team roles from system RBAC
- Creates swx_team_role table for team-scoped roles
- Adds team_role_id column to swx_team_member (replaces role_id)
- Seeds default team roles (owner, editor, viewer)

Bug #26: Team invitation system
- Creates swx_team_invitation table for team invitations

Run with: alembic upgrade head
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID


revision = "v2_7_26_team_roles_invitations"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bug #25: Create swx_team_role table
    op.create_table(
        "swx_team_role",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("permissions", JSONB, default={}),
        sa.Column("priority", sa.Integer, default=0),
        sa.Column("is_system", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    
    # Seed default team roles
    op.execute("""
        INSERT INTO swx_team_role (id, key, name, description, permissions, priority, is_system, created_at, updated_at)
        VALUES 
            (gen_random_uuid(), 'owner', 'Team Owner', 'Full control over team, including deletion and member management', 
             '{"can_edit": true, "can_delete": true, "can_invite": true, "can_remove": true, "can_change_roles": true, "can_manage_billing": true}',
             100, true, now(), now()),
            (gen_random_uuid(), 'editor', 'Team Editor', 'Can edit team content but cannot manage members or billing',
             '{"can_edit": true, "can_delete": false, "can_invite": false, "can_remove": false, "can_change_roles": false, "can_manage_billing": false}',
             50, true, now(), now()),
            (gen_random_uuid(), 'viewer', 'Team Viewer', 'Read-only access to team content',
             '{"can_edit": false, "can_delete": false, "can_invite": false, "can_remove": false, "can_change_roles": false, "can_manage_billing": false}',
             10, true, now(), now())
    """)
    
    # Bug #25: Add team_role_id column to swx_team_member
    op.add_column(
        "swx_team_member",
        sa.Column("team_role_id", PG_UUID(as_uuid=True), sa.ForeignKey("swx_team_role.id", ondelete="CASCADE"), nullable=True)
    )
    
    op.create_index("ix_swx_team_member_team_role_id", "swx_team_member", ["team_role_id"])
    
    # Migrate existing role_id to team_role_id
    # Map system roles to team roles:
    # - 'admin' or 'superadmin' -> 'owner' (team_key)
    # - 'member' or 'user' -> 'viewer' (team_key)
    # - others -> 'viewer'
    op.execute("""
        UPDATE swx_team_member tm
        SET team_role_id = (
            SELECT tr.id FROM swx_team_role tr
            WHERE tr.key = CASE 
                WHEN EXISTS (
                    SELECT 1 FROM swx_role r 
                    WHERE r.id = tm.role_id 
                    AND r.key IN ('admin', 'superadmin')
                ) THEN 'owner'
                ELSE 'viewer'
            END
        )
    """)
    
    # Make team_role_id NOT NULL after migration
    op.alter_column("swx_team_member", "team_role_id", nullable=False)
    
    # Drop old role_id column (optional - keep for backward compatibility during migration)
    # op.drop_column("swx_team_member", "role_id")
    
    # Bug #26: Create swx_team_invitation table
    op.create_table(
        "swx_team_invitation",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", PG_UUID(as_uuid=True), sa.ForeignKey("swx_team.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inviter_id", PG_UUID(as_uuid=True), sa.ForeignKey("swx_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invitee_email", sa.String(255), nullable=False),
        sa.Column("team_role_id", PG_UUID(as_uuid=True), sa.ForeignKey("swx_team_role.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.String(500)),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("accepted_at", sa.DateTime),
        sa.Column("rejected_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    
    # Create indexes for team_invitation
    op.create_index("ix_swx_team_invitation_email", "swx_team_invitation", ["invitee_email"])
    op.create_index("ix_swx_team_invitation_token", "swx_team_invitation", ["token"])
    op.create_index("ix_swx_team_invitation_status", "swx_team_invitation", ["status"])


def downgrade() -> None:
    # Bug #26: Drop swx_team_invitation table
    op.drop_index("ix_swx_team_invitation_status", "swx_team_invitation")
    op.drop_index("ix_swx_team_invitation_token", "swx_team_invitation")
    op.drop_index("ix_swx_team_invitation_email", "swx_team_invitation")
    op.drop_table("swx_team_invitation")
    
    # Bug #25: Remove team_role_id from swx_team_member
    op.drop_index("ix_swx_team_member_team_role_id", "swx_team_member")
    op.drop_column("swx_team_member", "team_role_id")
    
    # Bug #25: Drop swx_team_role table
    op.drop_table("swx_team_role")
