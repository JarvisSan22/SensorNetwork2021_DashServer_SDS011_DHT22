"""Database models (SQLModel over SQLite).

Two-tier time-series store per plan §3.1:
  - ReadingRaw    : every reading, short-lived live buffer (high fidelity)
  - Reading10Min  : permanent 10-min avg/min/max rollups
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlmodel import Field, SQLModel

from .timeutils import utcnow


class Placement(str, enum.Enum):
    indoor = "indoor"
    outdoor = "outdoor"


class Metric(str, enum.Enum):
    temperature_c = "temperature_c"
    humidity_pct = "humidity_pct"
    pm25 = "pm25"
    pm10 = "pm10"
    pressure_hpa = "pressure_hpa"


class Node(SQLModel, table=True):
    """A sensor node. `id` is a stable slug used as its ingest identity/token."""

    id: str = Field(primary_key=True)
    name: str = ""
    location: str = ""
    placement: Placement = Placement.indoor
    lat: float | None = None
    lon: float | None = None
    sensor_types: str = ""              # comma-separated, e.g. "DHT22,SDS011"
    firmware: str = ""
    report_interval_s: int = 10
    last_seen: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class ReadingRaw(SQLModel, table=True):
    """High-fidelity live buffer. Pruned after RAW_RETENTION_HOURS."""

    id: int | None = Field(default=None, primary_key=True)
    node_id: str = Field(index=True, foreign_key="node.id")
    ts: datetime = Field(index=True)
    metric: Metric = Field(index=True)
    value: float


class Reading10Min(SQLModel, table=True):
    """Permanent 10-minute rollups. Composite PK keeps upserts idempotent."""

    node_id: str = Field(primary_key=True, foreign_key="node.id")
    bucket: datetime = Field(primary_key=True, index=True)
    metric: Metric = Field(primary_key=True)
    avg: float
    min: float
    max: float
    samples: int


class WeatherReading(SQLModel, table=True):
    """Hourly snapshot of the configured location's outdoor weather (Open-Meteo).

    Kept as its own series — not a Node — so it can be overlaid on the node
    charts as a reference "outdoor" line without showing up as a device card,
    getting rolled up, or being pruned. One row per (hour, metric)."""

    ts: datetime = Field(primary_key=True)
    metric: Metric = Field(primary_key=True)
    value: float


class Setting(SQLModel, table=True):
    """Simple key/value store for app settings (location, units, ...)."""

    key: str = Field(primary_key=True)
    value: str = ""
