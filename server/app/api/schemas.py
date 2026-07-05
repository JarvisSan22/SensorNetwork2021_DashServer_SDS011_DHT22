"""Request/response shapes for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from ..models import Metric, Placement


class IngestPayload(BaseModel):
    """Body of POST /api/ingest sent by a node."""

    node: str
    readings: dict[Metric, float]
    # Optional metadata a node may self-report on first contact.
    name: str | None = None
    placement: Placement | None = None
    firmware: str | None = None
    sensor_types: list[str] | None = None


class MetricReading(BaseModel):
    metric: Metric
    value: float
    ts: datetime


class NodeSummary(BaseModel):
    id: str
    name: str
    placement: Placement
    location: str
    lat: float | None
    lon: float | None
    last_seen: datetime | None
    online: bool
    latest: list[MetricReading]


class SeriesPoint(BaseModel):
    ts: datetime
    value: float


class SeriesResponse(BaseModel):
    node_id: str
    metric: Metric
    tier: str           # "raw" or "10min"
    points: list[SeriesPoint]
