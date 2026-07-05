"""UTC time helpers.

We store timestamps as *naive UTC* datetimes (SQLite has no tz type). Incoming
API datetimes may be tz-aware (e.g. the browser sends ISO strings ending in
'Z'), so everything is normalized to naive UTC before it touches the DB.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current time as a naive UTC datetime (replaces datetime.utcnow())."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime) -> datetime:
    """Convert a possibly tz-aware datetime to naive UTC."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
