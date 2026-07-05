"""Typed access to the key/value Setting table (location, units, ...)."""

from __future__ import annotations

from pydantic import BaseModel
from sqlmodel import Session, select

from .models import Setting


class LocationSettings(BaseModel):
    location_name: str = ""
    lat: float | None = None
    lon: float | None = None


def get(session: Session, key: str, default: str = "") -> str:
    row = session.get(Setting, key)
    return row.value if row else default


def put(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
    else:
        row.value = value
    session.add(row)


def get_location(session: Session) -> LocationSettings:
    lat = get(session, "lat")
    lon = get(session, "lon")
    return LocationSettings(
        location_name=get(session, "location_name"),
        lat=float(lat) if lat else None,
        lon=float(lon) if lon else None,
    )


def set_location(session: Session, loc: LocationSettings) -> None:
    put(session, "location_name", loc.location_name or "")
    put(session, "lat", "" if loc.lat is None else str(loc.lat))
    put(session, "lon", "" if loc.lon is None else str(loc.lon))
    session.commit()


def all_settings(session: Session) -> dict[str, str]:
    return {s.key: s.value for s in session.exec(select(Setting)).all()}
