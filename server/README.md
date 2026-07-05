# SensorNet Home Server

Modern FastAPI + SQLite backend for the home sensor network: ingest, dashboard,
local weather, and ESP32 flashing. See
[`../Docs/APP_ARCHITECTURE.md`](../Docs/APP_ARCHITECTURE.md) for how it fits
together and [`../Docs/MODERNIZATION_PLAN.md`](../Docs/MODERNIZATION_PLAN.md) for
the design rationale.

## Run it (development)

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then visit:

- http://localhost:8000/ — the dashboard
- http://localhost:8000/docs — interactive API docs
- http://localhost:8000/health — liveness + DB check

For a real server (Docker or systemd), see
[`../Docs/DEPLOYMENT.md`](../Docs/DEPLOYMENT.md).

## Configuration

All via environment variables (no source editing):

| Variable | Default | Purpose |
|----------|---------|---------|
| `SENSORNET_DATA_DIR` | `server/data` | where the SQLite DB lives |
| `SENSORNET_DB_PATH` | `<data>/sensornet.db` | DB file path |
| `SENSORNET_HOST` / `SENSORNET_PORT` | `0.0.0.0` / `8000` | bind address |
| `SENSORNET_RAW_RETENTION_HOURS` | `24` | live raw-buffer retention (§3.1) |
| `SENSORNET_ROLLUP_MINUTES` | `10` | rollup bucket size (§3.1) |
| `SENSORNET_WIFI_SSID` / `SENSORNET_WIFI_PASS` | — | prefill the Add-a-node flash form |
| `SENSORNET_SERVER_URL` | derived | Server URL a flashed node reports to |

## Layout

```
app/
  main.py            FastAPI entrypoint, scheduler, static mount, "/" dashboard
  config.py          env-driven settings (.env loader)
  db.py              SQLite engine + session, init_db()
  models.py          SQLModel tables (Node, ReadingRaw, Reading10Min, WeatherReading, Setting)
  rollup.py          raw -> 10-min aggregation + prune job
  weatherlog.py      hourly weather snapshot job
  settings_store.py  location/settings key-value access
  timeutils.py       naive-UTC helpers
  api/               ingest, nodes, readings, weather, settings, flash routers
  services/          weather.py (Open-Meteo), flasher.py (esptool + serial)
  web/               templates/index.html, static/app.js, static/style.css
```

See [`../Docs/APP_ARCHITECTURE.md`](../Docs/APP_ARCHITECTURE.md) for the full map.
