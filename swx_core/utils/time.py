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