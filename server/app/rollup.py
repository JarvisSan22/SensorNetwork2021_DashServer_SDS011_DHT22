"""Rollup + prune job (plan §3.1).

Every ROLLUP_MINUTES:
  1. Aggregate raw readings into 10-min avg/min/max buckets (idempotent upsert).
  2. Delete raw readings older than RAW_RETENTION_HOURS (already rolled up).

Aggregation runs in SQL so it stays fast regardless of row count.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlmodel import Session

from .config import RAW_RETENTION_HOURS, ROLLUP_MINUTES
from .db import engine
from .timeutils import utcnow

# Upsert completed buckets. Bucket = ts floored to the rollup window.
# Only roll up buckets strictly before the *current* (still-filling) bucket.
_ROLLUP_SQL = text(
    """
    INSERT INTO reading10min (node_id, bucket, metric, avg, min, max, samples)
    SELECT
        node_id,
        datetime((CAST(strftime('%s', ts) AS INTEGER) / :w) * :w, 'unixepoch') AS bucket,
        metric,
        avg(value), min(value), max(value), count(*)
    FROM readingraw
    WHERE ts < :current_bucket
    GROUP BY node_id, metric, bucket
    ON CONFLICT(node_id, bucket, metric) DO UPDATE SET
        avg = excluded.avg,
        min = excluded.min,
        max = excluded.max,
        samples = excluded.samples
    """
)

_PRUNE_SQL = text("DELETE FROM readingraw WHERE ts < :cutoff")


def _floor_to_window(dt: datetime, window_s: int) -> datetime:
    """Floor a naive-UTC datetime to the rollup window (tz-offset safe)."""
    midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    secs = int((dt - midnight).total_seconds())
    return midnight + timedelta(seconds=(secs // window_s) * window_s)


def run_rollup(now: datetime | None = None) -> dict:
    """Run one rollup + prune cycle. Returns a small summary dict."""
    now = now or utcnow()
    window_s = ROLLUP_MINUTES * 60
    current_bucket = _floor_to_window(now, window_s)
    raw_cutoff = now - timedelta(hours=RAW_RETENTION_HOURS)

    with Session(engine) as session:
        session.exec(
            _ROLLUP_SQL, params={"w": window_s, "current_bucket": current_bucket}
        )
        result = session.exec(_PRUNE_SQL, params={"cutoff": raw_cutoff})
        pruned = result.rowcount or 0
        session.commit()

    return {
        "ran_at": now.isoformat(),
        "current_bucket": current_bucket.isoformat(),
        "raw_cutoff": raw_cutoff.isoformat(),
        "raw_pruned": pruned,
    }
