"""
Alembic Migration: v2.15.2 Convert system config fields to JSONB
=================================================================

Converts SystemConfig value/history fields and related metadata/permissions
columns from TEXT/JSON to JSONB so PostgreSQL stores native JSON values and
supports JSONB operators and indexing.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Run: alembic upgrade head
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "v2_15_2_jsonb_config"
down_revision: str | None = "v2_15_1_add_team_id"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE swx_system_config ALTER COLUMN value TYPE JSONB USING value::jsonb"))
    op.execute(sa.text("ALTER TABLE swx_system_config ALTER COLUMN metadata TYPE JSONB USING metadata::jsonb"))
    op.execute(sa.text("ALTER TABLE swx_system_config_history ALTER COLUMN old_value TYPE JSONB USING old_value::jsonb"))
    op.execute(sa.text("ALTER TABLE swx_system_config_history ALTER COLUMN new_value TYPE JSONB USING new_value::jsonb"))
    op.execute(sa.text("ALTER TABLE swx_system_config_history ALTER COLUMN metadata TYPE JSONB USING metadata::jsonb"))
    op.execute(sa.text("ALTER TABLE swx_team_role ALTER COLUMN permissions TYPE JSONB USING permissions::jsonb"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE swx_team_role ALTER COLUMN permissions TYPE JSON USING permissions::json"))
    op.execute(sa.text("ALTER TABLE swx_system_config_history ALTER COLUMN metadata TYPE JSON USING metadata::json"))
    op.execute(sa.text("ALTER TABLE swx_system_config_history ALTER COLUMN new_value TYPE TEXT USING new_value::text"))
    op.execute(sa.text("ALTER TABLE swx_system_config_history ALTER COLUMN old_value TYPE TEXT USING old_value::text"))
    op.execute(sa.text("ALTER TABLE swx_system_config ALTER COLUMN metadata TYPE JSON USING metadata::json"))
    op.execute(sa.text("ALTER TABLE swx_system_config ALTER COLUMN value TYPE TEXT USING value::text"))
