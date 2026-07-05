# Legacy (2020–2021) — archived, not run

This folder holds the original sensor-network code, kept for reference during the
rewrite. **Nothing here runs in the new system.** It is Python 2/3-mixed and
depends on removed library APIs. See [`../Docs/MODERNIZATION_PLAN.md`](../Docs/MODERNIZATION_PLAN.md).

| Path | What it was | Replaced by |
|------|-------------|-------------|
| `AQ_Plot_server/data_reciver.py` | Flask receiver, data-in-URL, CSV files | `server/` → `POST /api/ingest` + SQLite |
| `AQ_Plot_server/Index.py`, `dash_server*.py` | Plotly Dash dashboard (removed APIs) | `server/` dashboard (Phase 2) |
| `AQ_nodes/DHT22-Flasknode.ino` | ESP8266 firmware, GET-in-URL | `firmware/` PlatformIO + JSON POST |
| `AQ_run/Scripts/` | RPI local logging (SDS011/DHT/GPS) | `server/` collector (Phase 5); SDS011 protocol salvaged |
| `AQ_Plot/` | folium/vincent/mpld3 GPS walk maps | out of scope for v1 |
| `variables.py`, `variables_temp.py` | edit-a-Python-file config | `server/app/config.py` + Settings UI |

**Salvage targets** (porting forward, not running as-is):
- SDS011 serial command bytes / frame parsing — `AQ_run/Scripts/sds_rec.py`
- node-freshness "Active" check — `AQ_Plot_server/Index.py::StatueBoxes`
- historical CSVs — `AQ_run/data/*.csv` → imported into `readings_10min`
