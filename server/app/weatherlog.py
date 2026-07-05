"""Hourly weather logger.

Snapshots the configured location's outdoor weather into WeatherReading so it
can be plotted alongside the node data (a reference "outdoor" line). Runs on a
schedule from main.py's lifespan, plus once on boot to catch up.

Idempotent per hour: the timestamp is floored to the hour and upserted, so a
boot + the hourly tick landing in the same hour just overwrite one row.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session

from . import settings_store
from .db import engine
from .models import Metric, WeatherReading
from .services import weather as weather_svc
from .timeutils import utcnow

# Which live "current" fields map onto our stored metrics (same units as the
# node metrics, so they share the chart axes).
_FIELD_FOR_METRIC = {
    Metric.temperature_c: "temperature_c",
    Metric.humidity_pct: "humidity_pct",
}


def record_weather(now: datetime | None = None) -> dict:
    """Fetch + store one hourly weather snapshot. Never raises — returns a small
    status dict so both the boot call and the scheduler are safe."""
    now = now or utcnow()
    bucket = now.replace(minute=0, second=0, microsecond=0)

    with Session(engine) as session:
        loc = settings_store.get_location(session)
        if loc.lat is None or loc.lon is None:
            return {"stored": 0, "reason": "no location set"}

        try:
            data = weather_svc.get_weather(loc.lat, loc.lon)
        except Exception as exc:  # network/API hiccup — skip this tick
            return {"stored": 0, "reason": f"fetch failed: {exc}"}

        cur = data.get("current", {})
        stored = 0
        for metric, field in _FIELD_FOR_METRIC.items():
            value = cur.get(field)
            if value is None:
                continue
            row = session.get(WeatherReading, (bucket, metric))
            if row is None:
                session.add(WeatherReading(ts=bucket, metric=metric, value=value))
            else:
                row.value = value
            stored += 1
        session.commit()

    return {"stored": stored, "bucket": bucket.isoformat()}
