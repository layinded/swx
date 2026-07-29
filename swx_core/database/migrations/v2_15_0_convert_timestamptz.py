"""
Alembic Migration: v2.15.0 Convert TIMESTAMP to TIMESTAMPTZ
===========================================================

Converts all TIMESTAMP WITHOUT TIME ZONE columns to TIMESTAMP WITH TIME ZONE
across all swx_* tables. This is the data migration companion to the code
changes that made all Python datetimes timezone-aware (utc_now() returns
datetime.now(timezone.utc) without stripping tzinfo).

The migration uses a dynamic PL/pgSQL loop over information_schema.columns
so it automatically covers every swx_* table without hardcoding column names.

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "v2_15_0_timestamptz"
down_revision: Union[str, None] = None  # UPDATE THIS to your current head
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                col_record RECORD;
            BEGIN
                FOR col_record IN
                    SELECT
                        c.table_schema,
                        c.table_name,
                        c.column_name
                    FROM information_schema.columns c
                    JOIN information_schema.tables t
                        ON c.table_schema = t.table_schema
                        AND c.table_name = t.table_name
                    WHERE c.data_type = 'timestamp without time zone'
                        AND c.table_schema = 'public'
                        AND t.table_type = 'BASE TABLE'
                        AND c.table_name LIKE 'swx_%'
                LOOP
                    EXECUTE format(
                        'ALTER TABLE %I.%I ALTER COLUMN %I TYPE TIMESTAMPTZ USING %I AT TIME ZONE ''UTC''',
                        col_record.table_schema,
                        col_record.table_name,
                        col_record.column_name,
                        col_record.column_name
                    );
                END LOOP;
            END $$;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                col_record RECORD;
            BEGIN
                FOR col_record IN
                    SELECT
                        c.table_schema,
                        c.table_name,
                        c.column_name
                    FROM information_schema.columns c
                    JOIN information_schema.tables t
                        ON c.table_schema = t.table_schema
                        AND c.table_name = t.table_name
                    WHERE c.data_type = 'timestamp with time zone'
                        AND c.table_schema = 'public'
                        AND t.table_type = 'BASE TABLE'
                        AND c.table_name LIKE 'swx_%'
                LOOP
                    EXECUTE format(
                        'ALTER TABLE %I.%I ALTER COLUMN %I TYPE TIMESTAMP WITHOUT TIME ZONE USING %I AT TIME ZONE ''UTC''',
                        col_record.table_schema,
                        col_record.table_name,
                        col_record.column_name,
                        col_record.column_name
                    );
                END LOOP;
            END $$;
            """
        )
    )