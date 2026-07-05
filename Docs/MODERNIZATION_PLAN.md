# Sensor Network — Modernization Plan

> Goal: turn the 2020–2021 RPI/ESP8266 sensor-network code into a clean, simple
> **home-server** app that lets me:
> 1. See current indoor/outdoor conditions at a glance (temp, humidity, PM2.5/PM10).
> 2. Set my location and get a free current + today's weather report.
> 3. Add a new sensor node easily — plug an ESP into the server and flash it from the UI.

---

## 1. Where the project stands today

| Area | Current state | Verdict |
|------|---------------|---------|
| **Node firmware** (`AQ_nodes/DHT22-Flasknode.ino`) | ESP8266 reads DHT22, sends data as an **HTTP GET with values in the URL path**. WiFi creds hard-coded. | Rewrite. Keep the idea, change the transport + provisioning. |
| **Data receiver** (`AQ_Plot_server/data_reciver.py`) | Flask app, parses URL, appends to **CSV files** with bespoke multi-line headers. Python-2 leftovers (`.decode` on str). | Replace with a JSON API + database. |
| **Dashboard** (`AQ_Plot_server/Index.py`, `dash_server*.py`) | Plotly **Dash**, but uses removed APIs: `dash_core_components`, `dash_html_components`, `app.run_server`, pandas `error_bad_lines`. Fragile CSV globbing/parsing. | Rewrite UI on a current stack. Reuse the plotting *ideas*. |
| **Local RPI sensors** (`AQ_run/Scripts/`) | `start.py` + `sds_rec.py` (Py2 byte-string SDS011 driver) + `DHT.py` (deprecated `Adafruit_DHT`) + GPS + status. | Salvage the SDS011 serial protocol; modernize the rest. Optional component. |
| **GPS maps** (`AQ_Plot/`) | folium/vincent/mpld3 walk-route maps, lots of generated HTML in `Plots/`. | Out of scope for v1. Archive; revisit later. |
| **Config** (`variables_temp.py`) | Edit a Python file, copy to `variables.py`. | Replace with a config file + UI settings. |

**Core problems to fix:** Python 2/3 mix, removed library APIs, CSV-as-database,
unauthenticated URL-path ingestion, no weather, no easy way to add a node, no
indoor/outdoor concept.

---

## 2. Target architecture (v1)

One small, self-contained service that runs on the home server as a single
process (or one Docker container).

```
                ┌─────────────────────────────────────────────┐
   ESP nodes ──▶│  FastAPI app  (Python 3.11+)                 │
  (WiFi, JSON)  │  ┌─────────────┬───────────────┬──────────┐ │
                │  │ /api/ingest │ /api/weather  │ /api/flash│ │
                │  │ /api/nodes  │ /api/settings │           │ │
                │  └─────────────┴───────────────┴──────────┘ │
                │        │                                     │
                │   SQLite DB  (readings, nodes, settings)     │
                │        │                                     │
                │   Dashboard (HTML + Plotly.js, auto-refresh) │
                └─────────────────────────────────────────────┘
                          ▲                         │
                          │ Open-Meteo (free, no key)
                          └─────────────────────────┘
```

### Stack choices (recommended)

- **Backend:** **FastAPI** + Uvicorn. Async, typed, auto-docs at `/docs`, trivial JSON endpoints. Replaces both the Flask receiver and the old config plumbing.
- **Storage:** **SQLite** via SQLModel/SQLAlchemy. At home scale (a few nodes every 10 s) SQLite is plenty and needs zero setup. One file, easy backup. *(InfluxDB/TimescaleDB are options only if we ever outgrow this — we won't soon.)*
- **Dashboard:** server-rendered **HTML + Plotly.js**, auto-refreshing (HTMX or a tiny `fetch` poll). One stack, one process, no separate Node build. *(Alternatives: modernize the existing Plotly **Dash** app — lowest learning curve since it already exists; or **Streamlit** — fastest to build. Recommendation is plain FastAPI+Plotly.js to keep deploy to a single service, but Dash is a fine fallback if rewriting the UI from scratch feels like too much.)*
- **Weather:** **Open-Meteo** — free, no API key, gives current conditions + daily forecast from lat/lon. Geocode the location name once via its free geocoding endpoint.
- **Node firmware:** **PlatformIO** project for ESP8266/ESP32. Sends `POST /api/ingest` JSON with a device token. Uses **WiFiManager** captive portal so WiFi creds are entered on the device, not compiled in.
- **Easy flashing:** **server-side `esptool.py`** wrapper triggered from the dashboard ("Add node → pick sensor type → Flash"), since the described flow is *plugging the device into the server PC*. **ESP Web Tools** (browser Web-Serial flashing) is the alternative/complement for flashing from a laptop.

---

## 3. New data model

```
nodes
  id            (token / uuid)
  name          "Living Room", "Backyard"
  location      free text
  placement     enum: indoor | outdoor
  lat, lon      optional (for outdoor / weather compare)
  sensor_types  [DHT22, SDS011, ...]
  last_seen     timestamp
  firmware      version string

readings_raw         ← short-lived "live" buffer (high fidelity)
  id
  node_id  ──▶ nodes.id
  ts            timestamp (server receive time)
  metric        enum: temperature_c | humidity_pct | pm25 | pm10
  value         float
  -- auto-pruned after RAW_RETENTION (e.g. 24–48 h)

readings_10min       ← permanent rolled-up history (10-min buckets)
  node_id  ──▶ nodes.id
  bucket        timestamp (start of the 10-min window)
  metric        enum
  avg, min, max float     -- avg drives charts; min/max preserves spikes
  samples       int       -- how many raw points went into the bucket
  -- PRIMARY KEY (node_id, bucket, metric)

settings           (single row / key-value)
  location_name, lat, lon, units, weather_provider,
  raw_retention_hours, rollup_minutes, ...
```

**Why this shape:** "one row per (node, time, metric)" makes indoor/outdoor
grouping, current-state cards, and time-series queries trivial — no more parsing
CSV headers or guessing columns like the old `getdata()` did. Splitting **raw
buffer** from **10-min rollups** keeps the database small and fast forever (see §3.1).

### 3.1 Data retention & downsampling

The concern is real: at 10 s sampling, **one metric ≈ 8,640 rows/day**. A few
nodes × 4 metrics balloons into millions of rows in weeks, and charts slow to a
crawl. So we store data at two fidelities:

| Tier | Table | Resolution | Retention | Used for |
|------|-------|-----------|-----------|----------|
| **Live buffer** | `readings_raw` | every reading (~10 s) | short (default **24 h**, configurable) | the "Now" cards + zoomed-in *today* charts at full fidelity |
| **History** | `readings_10min` | 10-min `avg`/`min`/`max` | **permanent** (tiny) | all older charts and trends |

**How it works**

1. **Ingest** writes every reading into `readings_raw` (live data stays high-fidelity).
2. A **rollup job** runs every 10 min (background task / `APScheduler`): for each
   closed 10-min window it computes `avg`, `min`, `max`, `samples` per node+metric
   and upserts one row into `readings_10min`.
3. A **prune step** deletes `readings_raw` rows older than `raw_retention_hours`.
   The rollup has already captured them, so nothing of value is lost.

**Storage math:** 10-min rollups are **~144 rows/day/metric** vs. 8,640 raw —
a **60× reduction**, so years of history fit in a few MB. Keeping `min`/`max`
(not just the average) means pollution spikes and cold snaps still show up in
old data instead of being smoothed away.

**Charting logic:** the history view picks the tier by range — request inside the
raw-retention window → query `readings_raw` (full detail); anything older →
`readings_10min`. The user just sees one continuous chart; resolution drops
gracefully for older data, exactly as asked.

*(This raw-buffer + rollup pattern is what InfluxDB/Timescale do natively. We get
the same benefit on plain SQLite with a tiny scheduled job — no extra infra.)*

---

## 4. New ingestion contract (replaces URL-path GET)

Old: `GET /data/DHT22-Home/test,DHT-T,20,DHT-RH,50,192.168.x.x`

New:
```http
POST /api/ingest
Authorization: Bearer <node-token>
Content-Type: application/json

{
  "node": "living-room",
  "readings": { "temperature_c": 22.4, "humidity_pct": 48.1, "pm25": 7, "pm10": 12 }
}
```
Server timestamps on receipt, upserts `nodes.last_seen`, and inserts one
`readings_raw` row per metric (the 10-min rollup job later aggregates these into
`readings_10min` — see §3.1). A node is "online" if `last_seen` is within ~3× its
report interval (same idea as the old 10-minute "Active" check, generalized).

---

## 5. Proposed repository layout

```
/Docs/
  MODERNIZATION_PLAN.md         ← this file
/server/                        ← the new app
  app/
    main.py                     FastAPI entrypoint
    api/  ingest.py nodes.py weather.py flash.py settings.py
    db/   models.py session.py
    services/ weather.py flasher.py
    web/  templates/  static/   (dashboard)
  pyproject.toml
/firmware/                      ← was AQ_nodes/  (PlatformIO)
  dht22_node/      (DHT22 only)
  sds011_node/     (PM only)
  combo_node/      (DHT22 + SDS011)
  prebuilt/        compiled .bin files used by the flasher
/legacy/                        ← archived, kept for reference, not run
  AQ_Plot/  AQ_Plot_server/  AQ_run/  variables_temp.py
docker-compose.yml
README.md
```

---

## 6. What we keep, rewrite, or cut

**Keep / salvage**
- SDS011 serial command bytes & frame parsing from `AQ_run/Scripts/sds_rec.py` (port to Python 3 `bytes`).
- The "is this node active?" freshness logic from `Index.py` (`StatueBoxes`).
- Time-series + per-metric y-axis range idea from `update_figure`.
- Historical CSVs in `AQ_run/data/` — import into SQLite via a one-off migration script.

**Rewrite**
- ESP firmware → PlatformIO + JSON POST + WiFiManager.
- Receiver → FastAPI `/api/ingest`.
- Dashboard → FastAPI + Plotly.js.
- Config → SQLite settings + a Settings page.

**Cut from v1 (archive to `/legacy`)**
- folium/vincent/mpld3 GPS walk maps (`AQ_Plot/`) and all generated `Plots/*.html`.
- Blinkt!/LED logic, `ntplib` clock-sync, GPS time-as-clock setup.
- Bundled `Adafruit_DHT` C source (use `adafruit-circuitpython-dht` only if the server itself has a directly-attached DHT).

---

## 7. Phased delivery

Each phase is independently runnable so progress is visible early.

### Phase 0 — Scaffold (½ day)
- Create `/Docs` (done), `/server`, `/firmware`, `/legacy`; move old dirs into `/legacy`.
- New `server/` skeleton with FastAPI + SQLite + `/health`. Work on a feature branch.

### Phase 1 — Backend + ingestion + retention (2–3 days)
- DB models (`nodes`, `readings_raw`, `readings_10min`, `settings`).
- `POST /api/ingest`, `GET /api/nodes`, `GET /api/readings?node=&metric=&since=` (auto-selects raw vs. 10-min tier).
- **Rollup + prune job** (every 10 min): aggregate raw → `readings_10min`, then delete raw older than `raw_retention_hours` (§3.1).
- One-off `import_legacy_csv.py` to load `AQ_run/data/*.csv` straight into `readings_10min`.
- Verify with `curl` simulating a node + confirm rollup/prune runs.

### Phase 2 — Dashboard (2–3 days)
- **Now view:** cards grouped **Indoor / Outdoor**, each showing latest temp / humidity / PM2.5 / PM10 + online dot + "x min ago".
- **History view:** metric dropdown + date range → Plotly.js time-series (resampled), per-metric y-range.
- Auto-refresh every ~30 s.

### Phase 3 — Weather + location (1 day)
- Settings page: set location name → geocode → store lat/lon.
- `GET /api/weather` proxies Open-Meteo: current + today's high/low/precip/condition.
- Show a weather card next to the **Outdoor** sensors so real readings sit beside the forecast.

### Phase 4 — Easy "Add a Node" + new firmware (2–4 days)
- PlatformIO firmware for DHT22 / SDS011 / combo; first boot → WiFiManager AP for WiFi + server URL + token; then `POST /api/ingest`.
- Build `.bin`s into `firmware/prebuilt/`.
- **Add Node** UI: pick sensor type + name + indoor/outdoor → server runs `esptool.py` against the plugged-in serial device → registers the node + token. (ESP Web Tools as the browser-based alternative.)

### Phase 5 — Server-attached sensors (optional, 1–2 days)
- If SDS011/DHT hang directly off the server: a small `collector` process (modernized `sds_rec.py`) that POSTs to the same `/api/ingest`. Keeps one ingestion path.

### Phase 6 — Deploy + docs (1 day)
- `Dockerfile` + `docker-compose.yml` (app + persistent SQLite volume), or a `systemd` unit.
- Rewrite top-level `README.md` for the new setup; archive the old setup notes.

---

## 8. Open decisions (let's confirm before/while building)

1. **Dashboard stack:** FastAPI + Plotly.js (recommended) vs. modernized Dash vs. Streamlit?
2. **Node MCU:** stay on **ESP8266**, or move new nodes to **ESP32** (more headroom, BLE, better WiFi)? Plan supports both via PlatformIO.
3. **Flashing UX:** server-side `esptool.py` (matches "plug into the server PC") vs. browser ESP Web Tools — or both?
4. **PM sensor wiring:** SDS011 on the ESP node, or only on the server? Affects firmware variants.
5. **Keep GPS walk-mapping** as a later phase, or drop it entirely?
6. **Retention tuning (§3.1):** raw buffer = 24 h and rollups = 10-min averages by default — happy with those, or want a longer live buffer / finer (e.g. 5-min) or coarser (e.g. hourly) history?

---

## 9. First concrete steps

1. Confirm the decisions in §8.
2. Branch `modernize`, create the `/server` + `/firmware` + `/legacy` layout.
3. Stand up FastAPI + SQLite + `/api/ingest`, prove it with a `curl` post.
4. Build the Indoor/Outdoor "Now" dashboard against real + imported data.

---
*Drafted 2026-06-29. This is a living document — update it as decisions land.*
