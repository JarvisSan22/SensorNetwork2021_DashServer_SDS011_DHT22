# SensorNetwork — Home Air-Quality Server

A self-hosted server for a home sensor network: ESP32 nodes (SDS011 PM2.5/PM10,
DHT22 temp/humidity, BMP280 pressure) push readings over WiFi to a small FastAPI
app that stores them, shows a live dashboard, overlays local weather, and can
even **flash and configure new ESP32 nodes over USB** from the browser.

Author: Daniel Jarvis · jarvissan21@gmail.com
Successor to [SDS-011-Python](https://github.com/JarvisSan22/SDS-011-Python).
Feedback and contributions welcome.

---

## What it does

- **Ingest** — nodes `POST /api/ingest`; unknown nodes auto-register.
- **Store** — SQLite, two-tier: a 24h high-fidelity raw buffer + permanent
  10-minute rollups.
- **Dashboard** — live indoor/outdoor cards, overlaid per-node charts, a history
  explorer with a date-range picker and multi-node toggles, and local weather.
- **Weather** — pulls your location's conditions from Open-Meteo (no API key) and
  logs it hourly so it can be overlaid on the node charts.
- **Flash nodes** — plug an ESP32 into the server's USB, fill in the form, and the
  dashboard flashes the firmware and provisions WiFi + sensors — no phone needed.

---

## Quick start

Two supported ways to run it — pick one (full guide in
[Docs/DEPLOYMENT.md](Docs/DEPLOYMENT.md)):

### Option A — Docker
Best for a pure ingest + dashboard server; clean version-controlled updates.
```bash
sudo usermod -aG docker "$USER"   # one-time; then log out / back in
cp server/.env.example server/.env   # optional WiFi/server defaults
docker compose up -d --build
```
Your data lives in the separate `sensornet-data` volume, so rebuilding the app
never touches the database.

### Option B — Native (systemd + venv)
Best if this box **flashes ESP32 nodes** or reads USB/GPIO sensors — the process
reaches the hardware directly.
```bash
./deploy/install-native.sh
```

Either way the dashboard is at **http://<this-host>:8000/** (API docs at `/docs`).

> Flashing over USB is direct on the native install; on Docker it needs a device
> passthrough — see [Docs/DEPLOYMENT.md](Docs/DEPLOYMENT.md).

### Just hacking on it?
```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Repository layout

```
server/            the FastAPI app (ingest, dashboard, weather, flashing)
  app/             application code (see Docs/APP_ARCHITECTURE.md)
  collector/       optional host-side collector for USB/GPIO sensors
  scripts/         CSV import + demo-seed helpers
firmware/          prebuilt ESP32 images used by the flashing wizard
deploy/            native systemd unit + install script
docker-compose.yml + server/Dockerfile
Docs/              architecture, deployment, and the modernization plan
legacy/            the original 2019–2021 Dash/ESP8266 code, kept for reference
```

## Hardware

- **Server** — any Linux box or Raspberry Pi 3/4.
- **Sensor node** — ESP32 + DHT22 (and optionally SDS011/PMS5003 PM sensor, BMP280).
- **Server-attached sensors** (optional) — SDS011 over USB and/or DHT22 on GPIO,
  read by the local collector.

## Configuration

All via environment variables in `server/.env` (copy `server/.env.example`).
See the table in [server/README.md](server/README.md).

## Documentation

- [Docs/DEPLOYMENT.md](Docs/DEPLOYMENT.md) — Docker vs native, updates, backups.
- [Docs/APP_ARCHITECTURE.md](Docs/APP_ARCHITECTURE.md) — how the app is wired.
- [Docs/MODERNIZATION_PLAN.md](Docs/MODERNIZATION_PLAN.md) — design rationale & phases.
- [server/README.md](server/README.md) · [server/collector/README.md](server/collector/README.md)

## Legacy

The original Raspberry-Pi Plotly-Dash + ESP8266 project lives in [`legacy/`](legacy/).
Old setup video (2019): https://www.youtube.com/watch?v=fvaiyqwaWeM
