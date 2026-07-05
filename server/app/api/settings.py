"""Location/settings API.

PUT accepts either an explicit lat/lon or just a place name (geocoded via
Open-Meteo). This is what the dashboard's "Set location" form calls.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from .. import settings_store
from ..db import get_session
from ..services import weather

router = APIRouter(prefix="/api", tags=["settings"])


class LocationUpdate(BaseModel):
    location_name: str | None = None
    lat: float | None = None
    lon: float | None = None


@router.get("/settings")
def get_settings(session: Session = Depends(get_session)) -> settings_store.LocationSettings:
    return settings_store.get_location(session)


@router.put("/settings")
def update_settings(
    patch: LocationUpdate, session: Session = Depends(get_session)
) -> settings_store.LocationSettings:
    loc = settings_store.get_location(session)

    if patch.lat is not None and patch.lon is not None:
        loc.lat, loc.lon = patch.lat, patch.lon
        if patch.location_name:
            loc.location_name = patch.location_name
    elif patch.location_name:
        # Resolve a place name to coordinates.
        try:
            geo = weather.geocode(patch.location_name)
        except Exception as exc:  # network/API issue
            raise HTTPException(502, f"geocoding failed: {exc}") from exc
        if geo is None:
            raise HTTPException(404, f"no location found for '{patch.location_name}'")
        loc.location_name, loc.lat, loc.lon = geo.name, geo.lat, geo.lon

    settings_store.set_location(session, loc)
    return loc
