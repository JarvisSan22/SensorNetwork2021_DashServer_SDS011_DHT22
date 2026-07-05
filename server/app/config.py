"""Runtime configuration.

Kept deliberately small for Phase 0. Values come from environment variables so
the same code runs in dev, Docker, or systemd without editing source (a clean
break from the old `variables.py`-by-hand approach).
"""

from __future__ import annotations

import os
from pathlib import Path

# Project paths -------------------------------------------------------------
SERVER_DIR = Path(__file__).resolve().parent.parent          # .../server


def _load_dotenv(path: Path) -> None:
    """Minimal KEY=VALUE loader so a `server/.env` file can set config without
    adding a dependency. Real environment variables always win (setdefault)."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv(SERVER_DIR / ".env")

DATA_DIR = Path(os.getenv("SENSORNET_DATA_DIR", SERVER_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database ------------------------------------------------------------------
DB_PATH = Path(os.getenv("SENSORNET_DB_PATH", DATA_DIR / "sensornet.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Server --------------------------------------------------------------------
HOST = os.getenv("SENSORNET_HOST", "0.0.0.0")
PORT = int(os.getenv("SENSORNET_PORT", "8000"))
print(f"Server listening on {HOST}:{PORT} (DB: {DB_PATH})")

# Flashing defaults ---------------------------------------------------------
# Pre-fill the dashboard "Add a node" form so common WiFi/server values aren't
# retyped per device. Set in server/.env or the environment.
DEFAULT_WIFI_SSID = os.getenv("SENSORNET_WIFI_SSID", "")
DEFAULT_WIFI_PASS = os.getenv("SENSORNET_WIFI_PASS", "")


def _node_facing_url() -> str:
    """The URL nodes POST readings to, used as the form's Server URL default.

    Explicit SENSORNET_SERVER_URL wins; otherwise it's built from SENSORNET_HOST
    + SENSORNET_PORT. A bind-all host (0.0.0.0/::) isn't reachable by a node, so
    that yields "" and the dashboard falls back to the address the browser used.
    """
    explicit = os.getenv("SENSORNET_SERVER_URL", "")
    if explicit:
        return explicit
    host = HOST
    if not host or host in ("0.0.0.0", "::"):
        return ""
    if "://" not in host:
        host = "http://" + host
    return f"{host}:{PORT}"


DEFAULT_SERVER_URL = _node_facing_url()

# Retention / downsampling (§3.1 of the plan) -------------------------------
# Filled in for real in Phase 1; defined here so they have one home from day 1.
RAW_RETENTION_HOURS = int(os.getenv("SENSORNET_RAW_RETENTION_HOURS", "24"))
ROLLUP_MINUTES = int(os.getenv("SENSORNET_ROLLUP_MINUTES", "10"))
