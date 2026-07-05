"""GET /api/readings — time series with automatic raw/10-min tier selection.

The chart asks for a range; we serve full-fidelity raw data when the range
starts inside the live-buffer window, and the permanent 10-min averages for
anything older (plan §3.1). The caller just gets points + which tier was used.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from ..config import RAW_RETENTION_HOURS
from ..db import get_session
from ..models import Metric, Node, Reading10Min, ReadingRaw
from ..timeutils import to_naive_utc, utcnow
from .schemas import SeriesPoint, SeriesResponse

router = APIRouter(prefix="/api", tags=["readings"])


@router.get("/readings", response_model=SeriesResponse)
def readings(
    node: str,
    metric: Metric,
    since: datetime | None = Query(None, description="ISO start; default 24h ago"),
    until: datetime | None = Query(None, description="ISO end; default now"),
    session: Session = Depends(get_session),
) -> SeriesResponse:
    now = utcnow()
    until = to_naive_utc(until) if until else now
    since = to_naive_utc(since) if since else (now - timedelta(hours=24))

    # Small slack absorbs client/server clock skew so a request for ~the whole
    # retention window (e.g. the default "last 24h") reliably uses the raw tier.
    raw_cutoff = now - timedelta(hours=RAW_RETENTION_HOURS) - timedelta(minutes=5)

    if since >= raw_cutoff:
        rows = session.exec(
            select(ReadingRaw.ts, ReadingRaw.value)
            .where(
                ReadingRaw.node_id == node,
                ReadingRaw.metric == metric,
                ReadingRaw.ts >= since,
                ReadingRaw.ts <= until,
            )
            .order_by(ReadingRaw.ts)
        ).all()
        tier = "raw"
        points = [SeriesPoint(ts=ts, value=v) for ts, v in rows]
    else:
        rows = session.exec(
            select(Reading10Min.bucket, Reading10Min.avg)
            .where(
                Reading10Min.node_id == node,
                Reading10Min.metric == metric,
                Reading10Min.bucket >= since,
                Reading10Min.bucket <= until,
            )
            .order_by(Reading10Min.bucket)
        ).all()
        tier = "10min"
        points = [SeriesPoint(ts=b, value=v) for b, v in rows]

    return SeriesResponse(node_id=node, metric=metric, tier=tier, points=points)


@router.get("/readings/all")
def readings_all(
    metric: Metric,
    since: datetime | None = Query(None, description="ISO start; default 24h ago"),
    until: datetime | None = Query(None, description="ISO end; default now"),
    session: Session = Depends(get_session),
) -> dict:
    """One metric, every node — for the overlaid live charts. Same raw/10-min
    tier selection as /readings, grouped into one series per node."""
    now = utcnow()
    until = to_naive_utc(until) if until else now
    since = to_naive_utc(since) if since else (now - timedelta(hours=24))
    raw_cutoff = now - timedelta(hours=RAW_RETENTION_HOURS) - timedelta(minutes=5)

    if since >= raw_cutoff:
        rows = session.exec(
            select(ReadingRaw.node_id, ReadingRaw.ts, ReadingRaw.value)
            .where(ReadingRaw.metric == metric, ReadingRaw.ts >= since, ReadingRaw.ts <= until)
            .order_by(ReadingRaw.node_id, ReadingRaw.ts)
        ).all()
        tier = "raw"
    else:
        rows = session.exec(
            select(Reading10Min.node_id, Reading10Min.bucket, Reading10Min.avg)
            .where(Reading10Min.metric == metric, Reading10Min.bucket >= since, Reading10Min.bucket <= until)
            .order_by(Reading10Min.node_id, Reading10Min.bucket)
        ).all()
        tier = "10min"

    names = {n.id: n.name for n in session.exec(select(Node)).all()}
    series: dict[str, dict] = {}
    for node_id, ts, value in rows:
        s = series.get(node_id)
        if s is None:
            s = series[node_id] = {"node_id": node_id, "name": names.get(node_id, node_id), "points": []}
        s["points"].append({"ts": ts.isoformat(), "value": value})

    return {"metric": metric.value, "tier": tier, "series": list(series.values())}
