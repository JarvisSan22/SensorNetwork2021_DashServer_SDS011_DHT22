# App Architecture

A map of how the SensorNet home server fits together — data flow, endpoints, the
storage model, and where the dashboard lives — so future edits have a reference.

For the *why* and phased history, see [MODERNIZATION_PLAN.md](MODERNIZATION_PLAN.md).
This document describes the app **as it currently runs**.

---

## 1. What it is

A single FastAPI app that:

1. **Ingests** sensor readings from ESP32 nodes over HTTP (`POST /api/ingest`).
2. **Stores** them in SQLite as a two-tier time series (raw buffer + permanent
   10-minute rollups).
3. **Serves a dashboard** — live "now" cards, overlaid live charts, a history
   explorer, local weather, and an ESP32 flashing/provisioning wizard.
4. **Logs local weather** hourly from Open-Meteo so it can be overlaid on the
   node charts as an outdoor reference line.

Everything is server-rendered HTML + a single vanilla-JS file + Plotly. No build
step, no frontend framework.

---

## 2. Directory layout

```
server/
  app/
    main.py            FastAPI entrypoint, lifespan, scheduler, static mount, "/" route
    config.py          Env-driven config (.env loader, paths, retention constants)
    db.py              SQLite engine + session, init_db()
    models.py          SQLModel tables (see §4)
    timeutils.py       naive-UTC helpers (utcnow, to_naive_utc)
    settings_store.py  typed access to the key/value Setting table (location)
    rollup.py          raw -> 10-min aggregation + prune job
    weatherlog.py      hourly weather snapshot job
    api/
      ingest.py        POST /api/ingest        (nodes push readings)
      nodes.py         /api/nodes, /api/summary, PATCH+DELETE /api/nodes/{id}
      readings.py      /api/readings, /api/readings/all  (chart data)
      weather.py       /api/weather, /api/weather/history
      settings.py      GET/PUT /api/settings   (location)
      flash.py         /api/flash*             (ESP32 flashing/provisioning)
      schemas.py       Pydantic models for the API
    services/
      weather.py       Open-Meteo geocode + forecast (in-process cached)
      flasher.py       serial-port detection, esptool flashing, USB provisioning
    web/
      templates/index.html   the whole dashboard (Jinja2)
      static/app.js          all frontend behaviour
      static/style.css       all styling
  collector/           optional host-side collector (reads local sensors -> /api/ingest)
  scripts/             import_legacy_csv.py, seed_demo.py
  data/sensornet.db    the SQLite database
firmware/              prebuilt ESP32 images flashed by the flash API
```

---

## 3. Runtime & lifecycle

- **Entrypoint:** `app/main.py` builds the FastAPI `app`, includes every router,
  and mounts `/static`.
- **Startup (`lifespan`):**
  1. `db.init_db()` — create tables if missing.
  2. `run_rollup()` — catch up any pending rollup buckets.
  3. `record_weather()` — take a weather snapshot on boot (no-op if no location).
  4. Start an APScheduler `BackgroundScheduler` with two interval jobs:
     - **rollup** every `ROLLUP_MINUTES` (default 10 min)
     - **weatherlog** every 1 hour
- **Shutdown:** scheduler stops.
- **Run locally:** `cd server && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
  → dashboard at `/`, API docs at `/docs`, health at `/health`.

---

## 4. Data model (`app/models.py`)

All timestamps are **naive UTC** (SQLite has no tz type; incoming ISO strings are
normalized via `timeutils.to_naive_utc`).

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `Node` | one sensor device | `id` (PK, the ingest identity/slug), `name`, `placement` (indoor/outdoor), `location`, `lat/lon`, `sensor_types`, `firmware`, `last_seen` |
| `ReadingRaw` | high-fidelity live buffer, pruned after `RAW_RETENTION_HOURS` (24h) | `node_id`, `ts`, `metric`, `value` |
| `Reading10Min` | permanent 10-min avg/min/max rollups | PK `(node_id, bucket, metric)`, `avg/min/max/samples` |
| `WeatherReading` | hourly outdoor-weather snapshots for the saved location | PK `(ts, metric)`, `value` — only `temperature_c` + `humidity_pct` are stored |
| `Setting` | key/value app settings (location) | `key` (PK), `value` |

**`Metric` enum:** `temperature_c`, `humidity_pct`, `pm25`, `pm10`, `pressure_hpa`.

---

## 5. Data flow

### Ingest → store → serve
```
ESP32 node ──POST /api/ingest──▶ ReadingRaw (one row per metric, ts=now)
                                     │  (unknown nodes auto-register)
                    rollup job every 10 min
                                     ▼
                          Reading10Min (10-min avg/min/max, idempotent upsert)
                                     │  then prune ReadingRaw older than 24h
```

### Tiered reads (`app/api/readings.py`)
Both `/api/readings` (one node) and `/api/readings/all` (every node, one series
each) pick a tier from the requested `since`:
- `since` within the last ~24h → **raw** tier (full fidelity).
- older → **10min** tier (permanent rollups).
The response reports which `tier` was used.

### Weather logging (`app/weatherlog.py`)
```
hourly job ─▶ settings_store.get_location() ─▶ services.weather.get_weather(lat,lon)
          ─▶ upsert WeatherReading for temperature_c + humidity_pct (ts floored to the hour)
```
`record_weather()` never raises (returns a status dict) so a failed API call just
skips that tick. Served back via `/api/weather/history?metric=&since=&until=`.

---

## 6. API surface

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/ingest` | node pushes readings; auto-registers unknown nodes |
| GET | `/api/nodes` | raw list of `Node` rows |
| GET | `/api/summary` | dashboard "now" view: per-node latest reading, online state |
| PATCH | `/api/nodes/{id}` | edit node metadata (name, placement, location, ...) |
| DELETE | `/api/nodes/{id}` | remove a node **and all its readings** |
| GET | `/api/readings` | one node + metric time series (tiered) |
| GET | `/api/readings/all` | all nodes for one metric, one series each (tiered) |
| GET | `/api/weather` | current conditions + today's forecast for saved location |
| GET | `/api/weather/history` | stored hourly weather series for a metric |
| GET/PUT | `/api/settings` | get/set location (PUT geocodes a place name) |
| GET | `/api/flash` | detected serial ports, available firmware, pin setup, defaults |
| POST | `/api/flash` | flash firmware + provision WiFi/sensors over USB |
| POST | `/api/flash/monitor` | read serial output from a port for N seconds |
| GET | `/health` | liveness + DB ping |

All routers use prefix `/api` (flash uses `/api/flash`).

---

## 7. Frontend (`app/web/`)

Single Jinja2 template + `app.js` + `style.css`. The page auto-refreshes every
30s via `loop()` in `app.js`; a per-second clock ticks separately.

**Sections of `index.html` and what feeds them:**

| Section | Data source | Notes |
|---------|-------------|-------|
| Settings panel (⚙️) | `/api/settings` | edit location; also hosts the Add-a-node wizard |
| Add a node | `/api/flash` (+ POST) | 3-row field grid; sensors are blue/grey **toggle buttons** (hidden checkbox holds state) |
| Indoor / Outdoor cards | `/api/summary` | each card has ⚙️ edit + 🗑️ delete icon buttons |
| Weather card | `/api/weather` | current conditions for saved location |
| Live — all nodes | `/api/readings/all` (+ `/api/weather/history`) | temp + humidity overlaid per node; **Range** dropdown; **☁️ Outdoor weather** toggle overlays a dashed line |
| History | `/api/readings/all` (+ `/api/weather/history`) | **From/To date pickers**; nodes chosen via multi-select **toggle chips** (overlay several); a **☁️ Weather** chip overlays the outdoor line |

**Frontend conventions (in `app.js`):**
- `colorFor(nodeId)` assigns a **stable colour per node**, reused across the live
  charts, history traces, and chip dots, so a node is the same colour everywhere.
- Weather traces use a fixed grey (`WEATHER_COLOR`) drawn **dashed**; the weather
  chip/toggle uses the sentinel id `WEATHER_ID = "__weather__"`.
- Card buttons and history chips are wired with **event delegation**, so they
  survive the 30s re-render.
- Node edit/delete call PATCH/DELETE then `refreshCards()`.

**Cache-busting:** `main.py:asset_version()` returns the newest static-file mtime;
the template appends it as `?v=...` to `app.js`/`style.css`. Editing either file
changes the token, so browsers always fetch the fresh copy (no stale-JS surprises).

---

## 8. External services & config

- **Open-Meteo** (`app/services/weather.py`) — free, no API key. Geocoding
  (place name → lat/lon) and forecast (current + today). Results cached
  in-process for 10 min (`CACHE_TTL_S`) so the 30s dashboard refresh and the
  hourly logger don't hammer it.
- **Config** (`app/config.py`) — loads `server/.env` (real env vars win). Key vars:
  `SENSORNET_DB_PATH`, `SENSORNET_HOST/PORT`, `SENSORNET_WIFI_SSID/PASS`,
  `SENSORNET_SERVER_URL`, `SENSORNET_RAW_RETENTION_HOURS` (24),
  `SENSORNET_ROLLUP_MINUTES` (10). Add-a-node form defaults come from these.

---

## 9. Getting data in

- **ESP32 nodes** — flashed via the dashboard (`/api/flash`, `services/flasher.py`)
  or the captive-portal fallback; they `POST /api/ingest` on their report interval.
  Firmware images live in `firmware/`; wiring is mirrored in `flash.py:PIN_SETUP`.
- **Host collector** (`server/collector/`) — optional; reads locally attached
  sensors (SDS011/DHT22) and POSTs to `/api/ingest`. Supports `--simulate` and
  `--dry-run` for testing without hardware.
- **Legacy import / demo** — `scripts/import_legacy_csv.py`, `scripts/seed_demo.py`.
