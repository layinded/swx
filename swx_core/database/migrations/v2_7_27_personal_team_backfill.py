"""
Migration: Bug #7/29 - Personal team backfill for existing users

Creates personal teams for users without tenant_id and sets their tenant_id.

Run with: alembic upgrade head
"""

from typing import Union
from alembic import op
from sqlalchemy import text


revision: str = "v2_7_27_personal_team_backfill"
down_revision: Union[str, None] = None
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    owner_role_result = conn.execute(
        text("SELECT id FROM swx_team_role WHERE key = 'owner'")
    )
    owner_role_id = owner_role_result.scalar()
    
    if not owner_role_id:
        return
    
    users_without_tenant = conn.execute(
        text("""
            SELECT id, email, full_name
            FROM swx_users
            WHERE tenant_id IS NULL
        """)
    ).fetchall()
    
    for user_id, email, full_name in users_without_tenant:
        team_result = conn.execute(
            text("""
                INSERT INTO swx_team (id, name, description, owner_id, created_at, updated_at)
                VALUES (gen_random_uuid(), :name, 'Personal team', :owner_id, now(), now())
                RETURNING id
            """),
            {"name": f"{full_name or email}'s Team", "owner_id": user_id},
        )
        team_id = team_result.scalar()
        
        conn.execute(
            text("""
                INSERT INTO swx_team_member (id, team_id, user_id, team_role_id, created_at, updated_at)
                VALUES (gen_random_uuid(), :team_id, :user_id, :team_role_id, now(), now())
            """),
            {"team_id": team_id, "user_id": user_id, "team_role_id": owner_role_id},
        )
        
        conn.execute(
            text("UPDATE swx_users SET tenant_id = :team_id WHERE id = :user_id"),
            {"team_id": team_id, "user_id": user_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    
    personal_teams = conn.execute(
        text("""
            SELECT t.id, t.owner_id
            FROM swx_team t
            WHERE t.description = 'Personal team'
        """)
    ).fetchall()
    
    for team_id, owner_id in personal_teams:
        conn.execute(
            text("DELETE FROM swx_team_member WHERE team_id = :team_id"),
            {"team_id": team_id},
        )
        conn.execute(
            text("UPDATE swx_users SET tenant_id = NULL WHERE id = :owner_id"),
            {"owner_id": owner_id},
        )
        conn.execute(
            text("DELETE FROM swx_team WHERE id = :team_id"),
            {"team_id": team_id},
        )