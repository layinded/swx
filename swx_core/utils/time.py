"""Time utilities for timezone-aware UTC timestamps.

All framework code should use ``utc_now()`` instead of
``datetime.now(timezone.utc).replace(tzinfo=None)`` or ``datetime.utcnow()``.
Storing timezone-aware datetimes ensures unambiguous timestamp comparisons
across server timezone changes, container migrations, and daylight saving
boundaries.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def ensure_aware(dt: datetime | None) -> datetime | None:
    """Coerce a datetime to timezone-aware UTC.

    PostgreSQL ``TIMESTAMP WITHOUT TIME ZONE`` columns load as naive datetimes
    even when the SQLModel column declares ``DateTime(timezone=True)``.
    Comparing a naive value with ``utc_now()`` (which is timezone-aware)
    raises ``TypeError`` in Python 3.12+.

    This helper normalises any datetime to timezone-aware UTC so that
    ``ensure_aware(col_value) < utc_now()`` always works regardless of
    whether the migration converting the column to ``TIMESTAMPTZ`` has
    been applied.

    Args:
        dt: A datetime that may be naive or aware, or ``None``.

    Returns:
        The same datetime with ``tzinfo=timezone.utc`` if it was naive,
        unchanged if already aware, or ``None`` if the input was ``None``.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt