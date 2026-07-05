"""Import old legacy/AQ_run/data/*.csv into the 10-min rollup table.

    cd server && python -m scripts.import_legacy_csv ../legacy/AQ_run/data

Legacy format (best-effort): 4 metadata lines, then a header row, then data.
  line 1: Time Period,...
  line 2: Sensors:,<name>,...
  line 3: Location:,<loc>,Lat-Lon,<lat>,<lon>,...
  line 4: Interval time,<n>,...
  line 5: time,[lat,lon,alt,]DHT-RH,DHT-T,sds-pm2.5,sds-pm10,...
Old column -> metric mapping handles the messy real-world headers.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from app.db import engine, init_db
from app.models import Metric, Node, Placement, Reading10Min

COL_MAP = {
    "DHT-T": Metric.temperature_c,
    "DHT-RH": Metric.humidity_pct,
    "sds-pm2.5": Metric.pm25,
    "sds-pm10": Metric.pm10,
}


def parse_ts(raw: str) -> datetime | None:
    raw = raw.strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def floor10(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 10) * 10, second=0, microsecond=0)


def import_file(path: Path, session: Session) -> int:
    lines = path.read_text(errors="replace").splitlines()
    if len(lines) < 6:
        return 0

    loc_parts = lines[2].split(",")
    location = loc_parts[1].strip() if len(loc_parts) > 1 else path.stem
    node_id = location.lower().replace(" ", "-") or path.stem.lower()
    lat = lon = None
    try:
        lat, lon = float(loc_parts[3]), float(loc_parts[4])
    except (IndexError, ValueError):
        pass

    node = session.get(Node, node_id) or Node(id=node_id)
    node.name = location or node_id
    node.placement = Placement.outdoor if "gps" in node_id else Placement.indoor
    node.lat, node.lon = lat, lon
    session.add(node)

    header = next(csv.reader([lines[4]]))
    metric_cols = {i: COL_MAP[c] for i, c in enumerate(header) if c in COL_MAP}

    # bucket -> metric -> list of values
    buckets: dict[datetime, dict[Metric, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in csv.reader(lines[5:]):
        if not row:
            continue
        ts = parse_ts(row[0])
        if ts is None:
            continue
        b = floor10(ts)
        for i, metric in metric_cols.items():
            if i < len(row):
                try:
                    val = float(row[i])
                except ValueError:
                    continue
                if val != val:  # NaN
                    continue
                buckets[b][metric].append(val)

    count = 0
    for b, metrics in buckets.items():
        for metric, vals in metrics.items():
            if not vals:
                continue
            session.merge(Reading10Min(
                node_id=node_id, bucket=b, metric=metric,
                avg=round(sum(vals) / len(vals), 3),
                min=min(vals), max=max(vals), samples=len(vals),
            ))
            count += 1
    return count


def main(folder: str) -> None:
    init_db()
    files = sorted(Path(folder).glob("*.csv"))
    if not files:
        print(f"No CSVs found in {folder}")
        return
    total = 0
    with Session(engine) as session:
        for f in files:
            n = import_file(f, session)
            print(f"  {f.name}: {n} buckets")
            total += n
        session.commit()
    print(f"Imported {total} rollup rows from {len(files)} files.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../legacy/AQ_run/data")
