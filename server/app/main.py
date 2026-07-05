"""FastAPI entrypoint.

Run locally:
    cd server
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Dashboard: http://localhost:8000/   ·   API docs: http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from . import __version__, config, db
from .api import flash, ingest, nodes, readings, settings, weather
from .rollup import run_rollup
from .weatherlog import record_weather

WEB_DIR = Path(__file__).resolve().parent / "web"
STATIC_DIR = WEB_DIR / "static"
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def asset_version() -> str:
    """Cache-busting token = newest static-file mtime. Changes whenever we edit
    app.js/style.css, so browsers fetch the fresh file instead of a stale copy."""
    try:
        return str(int(max(p.stat().st_mtime for p in STATIC_DIR.glob("*"))))
    except ValueError:
        return __version__

scheduler = BackgroundScheduler(daemon=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    run_rollup()  # catch up any pending buckets on boot
    record_weather()  # snapshot current weather on boot (no-op if no location)
    scheduler.add_job(
        run_rollup,
        "interval",
        minutes=config.ROLLUP_MINUTES,
        id="rollup",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        record_weather,
        "interval",
        hours=1,
        id="weatherlog",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="SensorNet Home Server",
    version=__version__,
    summary="Ingest, dashboard, weather and node-flashing for the home sensor network.",
    lifespan=lifespan,
)

app.include_router(ingest.router)
app.include_router(nodes.router)
app.include_router(readings.router)
app.include_router(settings.router)
app.include_router(weather.router)
app.include_router(flash.router)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/health")
def health() -> JSONResponse:
    try:
        db_ok = db.ping()
    except Exception as exc:  # pragma: no cover
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": False, "error": str(exc)},
        )
    return JSONResponse(
        {"status": "ok", "version": __version__, "database": db_ok, "db_path": str(config.DB_PATH)}
    )


@app.get("/")
def dashboard(request: Request):
    """Indoor/Outdoor 'Now' dashboard + history chart (Phase 2)."""
    return templates.TemplateResponse(request, "index.html", {
        "version": __version__,
        "asset_ver": asset_version(),
        "default_wifi_ssid": config.DEFAULT_WIFI_SSID,
        "default_wifi_pass": config.DEFAULT_WIFI_PASS,
        "default_server_url": config.DEFAULT_SERVER_URL,
    })
