"""Weather endpoints — live conditions and the stored hourly history."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from .. import settings_store
from ..db import get_session
from ..models import Metric, WeatherReading
from ..services import weather as weather_svc
from ..timeutils import to_naive_utc, utcnow

router = APIRouter(prefix="/api", tags=["weather"])


@router.get("/weather")
def get_weather(session: Session = Depends(get_session)) -> dict:
    loc = settings_store.get_location(session)
    if loc.lat is None or loc.lon is None:
        raise HTTPException(404, "location not set — set it in Settings first")
    try:
        data = weather_svc.get_weather(loc.lat, loc.lon)
    except Exception as exc:
        raise HTTPException(502, f"weather fetch failed: {exc}") from exc
    return {"location": loc.model_dump(), **data}


@router.get("/weather/history")
def weather_history(
    metric: Metric,
    since: datetime | None = Query(None, description="ISO start; default 24h ago"),
    until: datetime | None = Query(None, description="ISO end; default now"),
    session: Session = Depends(get_session),
) -> dict:
    """Stored hourly weather series for one metric — the reference "outdoor"
    line overlaid on the node charts. Empty for metrics we don't record
    (only temperature_c / humidity_pct are stored)."""
    now = utcnow()
    until = to_naive_utc(until) if until else now
    since = to_naive_utc(since) if since else (now - timedelta(hours=24))

    rows = session.exec(
        select(WeatherReading.ts, WeatherReading.value)
        .where(
            WeatherReading.metric == metric,
            WeatherReading.ts >= since,
            WeatherReading.ts <= until,
        )
        .order_by(WeatherReading.ts)
    ).all()

    return {
        "metric": metric.value,
        "points": [{"ts": ts.isoformat(), "value": v} for ts, v in rows],
    }
