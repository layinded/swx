"""
Alembic Migration: v2.18.0 Add FLOAT (and aliases) to settingvaluetype enum
==========================================================================

Extends the PostgreSQL ``settingvaluetype`` enum with three new values:
``float``, ``integer``, and ``boolean``.

- ``float`` — new scalar type for floating-point config values.
- ``integer`` — alias for ``int`` (FastPII convention).
- ``boolean`` — alias for ``bool`` (FastPII convention).

USAGE:
1. Copy this file to your project's migrations/versions/ directory
2. Update 'down_revision' to point to your current head
3. Run: alembic upgrade head

NOTE: ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction in
PostgreSQL < 12.  The ``autocommit_block()`` context manager handles
this correctly across PG versions.  ``IF NOT EXISTS`` (PG 12+) makes
the migration idempotent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2_18_0_float_enum"
down_revision: str | None = None  # UPDATE THIS to your current head
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(sa.text("ALTER TYPE settingvaluetype ADD VALUE IF NOT EXISTS 'float'"))
        op.execute(sa.text("ALTER TYPE settingvaluetype ADD VALUE IF NOT EXISTS 'integer'"))
        op.execute(sa.text("ALTER TYPE settingvaluetype ADD VALUE IF NOT EXISTS 'boolean'"))


def downgrade() -> None:
    # PostgreSQL does not support removing individual enum values.
    # To fully revert, recreate the enum type without the new values
    # and re-cast the column.  This is intentionally a no-op downgrade —
    # the new values are additive and harmless if unused.
    pass
