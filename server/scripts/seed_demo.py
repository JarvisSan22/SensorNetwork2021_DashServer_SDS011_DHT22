"""Seed demo nodes + readings so the dashboard has something to show.

    cd server && python -m scripts.seed_demo

Inserts two nodes (one indoor, one outdoor), ~2h of raw readings (drives the
'Now' cards and recent chart) and 7 days of 10-min rollups (drives the older
history tier). Safe to re-run; clears prior demo rows first.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from sqlmodel import Session, delete, select

from app.db import engine, init_db
from app.models import Metric, Node, Placement, Reading10Min, ReadingRaw
from app.timeutils import utcnow

DEMO = {
    "living-room": dict(name="Living Room", placement=Placement.indoor,
                        metrics={Metric.temperature_c: 22, Metric.humidity_pct: 45}),
    "backyard": dict(name="Backyard", placement=Placement.outdoor, lat=34.78, lon=135.47,
                     metrics={Metric.temperature_c: 18, Metric.humidity_pct: 60,
                              Metric.pm25: 9, Metric.pm10: 14}),
}


def wave(base: float, t: datetime, amp: float) -> float:
    """Smooth daily cycle + noise."""
    frac = (t.hour * 60 + t.minute) / 1440 * 2 * math.pi
    return round(base + amp * math.sin(frac) + random.uniform(-amp / 4, amp / 4), 2)


def main() -> None:
    init_db()
    now = utcnow()
    with Session(engine) as s:
        for node_id, cfg in DEMO.items():
            # reset
            s.exec(delete(ReadingRaw).where(ReadingRaw.node_id == node_id))
            s.exec(delete(Reading10Min).where(Reading10Min.node_id == node_id))

            node = s.get(Node, node_id) or Node(id=node_id)
            node.name = cfg["name"]
            node.placement = cfg["placement"]
            node.lat = cfg.get("lat")
            node.lon = cfg.get("lon")
            node.sensor_types = "DHT22" if node_id == "living-room" else "DHT22,SDS011"
            node.last_seen = now
            s.add(node)

            amps = {Metric.temperature_c: 3, Metric.humidity_pct: 10,
                    Metric.pm25: 4, Metric.pm10: 6}

            # 7 days of 10-min rollups
            t = now - timedelta(days=7)
            while t < now - timedelta(hours=2):
                for metric, base in cfg["metrics"].items():
                    v = wave(base, t, amps[metric])
                    s.add(Reading10Min(node_id=node_id, bucket=t, metric=metric,
                                       avg=v, min=v - 1, max=v + 1, samples=60))
                t += timedelta(minutes=10)

            # last 2h of raw readings every 30s
            t = now - timedelta(hours=2)
            while t <= now:
                for metric, base in cfg["metrics"].items():
                    s.add(ReadingRaw(node_id=node_id, ts=t, metric=metric,
                                     value=wave(base, t, amps[metric])))
                t += timedelta(seconds=30)

        s.commit()

    with Session(engine) as s:
        print("nodes:", [n.id for n in s.exec(select(Node)).all()])
    print("Seeded demo data. Start the server and open http://localhost:8000/")


if __name__ == "__main__":
    main()
