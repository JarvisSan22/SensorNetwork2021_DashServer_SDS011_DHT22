"""Local sensor collector — reads attached sensors, POSTs to /api/ingest.

Examples:
    # SDS011 on USB + DHT22 on GPIO pin 4, reporting as an indoor node
    python -m collector.run --server http://localhost:8000 --node server-room \
        --placement indoor --sds-port /dev/ttyUSB0 --dht-pin 4

    # Dry run (print payloads, don't POST) / one shot
    python -m collector.run --sds-port /dev/ttyUSB0 --once --dry-run

    # No hardware: synthesize readings (useful to smoke-test the server)
    python -m collector.run --simulate --node test-collector --once
"""

from __future__ import annotations

import argparse
import random
import sys
import time

import httpx

from .sds011 import SDS011


def build_payload(args, readings: dict) -> dict:
    sensors = []
    if "pm25" in readings:
        sensors.append("SDS011")
    if "temperature_c" in readings:
        sensors.append("DHT22")
    return {
        "node": args.node,
        "placement": args.placement,
        "firmware": "collector-1.0",
        "sensor_types": sensors,
        "readings": readings,
    }


def collect(args, sds: SDS011 | None) -> dict:
    readings: dict[str, float] = {}

    if args.simulate:
        readings["temperature_c"] = round(random.uniform(18, 26), 1)
        readings["humidity_pct"] = round(random.uniform(40, 70), 1)
        readings["pm25"] = round(random.uniform(3, 25), 1)
        readings["pm10"] = round(random.uniform(5, 40), 1)
        return readings

    if sds is not None:
        pm = sds.read_average(samples=args.sds_samples)
        if pm is not None:
            readings["pm25"], readings["pm10"] = pm
        else:
            print("  SDS011: no valid frame this cycle", file=sys.stderr)

    if args.dht_pin is not None:
        from .dht import DHTUnavailable, read_dht
        try:
            t, h = read_dht(args.dht_pin)
            readings["temperature_c"], readings["humidity_pct"] = round(t, 1), round(h, 1)
        except DHTUnavailable as exc:
            print(f"  DHT22: {exc}", file=sys.stderr)

    return readings


def post(args, payload: dict) -> None:
    if args.dry_run:
        print("DRY-RUN payload:", payload)
        return
    try:
        r = httpx.post(f"{args.server}/api/ingest", json=payload, timeout=10)
        r.raise_for_status()
        print(f"  -> {args.server}/api/ingest {r.json()}")
    except Exception as exc:
        print(f"  POST failed: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SensorNet local collector")
    p.add_argument("--server", default="http://localhost:8000")
    p.add_argument("--node", default="server-collector")
    p.add_argument("--placement", default="indoor", choices=["indoor", "outdoor"])
    p.add_argument("--sds-port", default=None, help="serial port for SDS011, e.g. /dev/ttyUSB0")
    p.add_argument("--sds-samples", type=int, default=5)
    p.add_argument("--dht-pin", type=int, default=None, help="GPIO pin for DHT22 (RPi)")
    p.add_argument("--interval", type=float, default=30.0, help="seconds between reports")
    p.add_argument("--once", action="store_true", help="single read then exit")
    p.add_argument("--dry-run", action="store_true", help="print payloads, don't POST")
    p.add_argument("--simulate", action="store_true", help="synthesize readings (no hardware)")
    args = p.parse_args(argv)

    if not args.simulate and not args.sds_port and args.dht_pin is None:
        p.error("provide --sds-port and/or --dht-pin, or use --simulate")

    sds = None
    if args.sds_port and not args.simulate:
        try:
            sds = SDS011(args.sds_port)
        except Exception as exc:
            print(f"Could not open SDS011 on {args.sds_port}: {exc}", file=sys.stderr)
            return 1

    print(f"Collector node='{args.node}' ({args.placement}) -> {args.server} "
          f"every {args.interval}s  [sds={bool(sds)} dht={args.dht_pin} sim={args.simulate}]")
    try:
        while True:
            readings = collect(args, sds)
            if readings:
                post(args, build_payload(args, readings))
            else:
                print("  no readings this cycle", file=sys.stderr)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        if sds:
            sds.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
