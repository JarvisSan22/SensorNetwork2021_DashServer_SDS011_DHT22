"""Open-Meteo weather + geocoding (free, no API key).

- geocode(name)      -> resolve a place name to lat/lon
- get_weather(lat,lon) -> current conditions + today's forecast

Results are cached in-process for a few minutes so the dashboard's 30s refresh
doesn't hammer the API.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL_S = 600  # 10 min

# WMO weather codes -> (text, emoji). Condensed to the common buckets.
_WMO = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"), 2: ("Partly cloudy", "⛅"), 3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"), 48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Dense drizzle", "🌧️"),
    61: ("Light rain", "🌦️"), 63: ("Rain", "🌧️"), 65: ("Heavy rain", "🌧️"),
    66: ("Freezing rain", "🌧️"), 67: ("Freezing rain", "🌧️"),
    71: ("Light snow", "🌨️"), 73: ("Snow", "🌨️"), 75: ("Heavy snow", "❄️"),
    77: ("Snow grains", "🌨️"),
    80: ("Rain showers", "🌦️"), 81: ("Rain showers", "🌧️"), 82: ("Violent showers", "⛈️"),
    85: ("Snow showers", "🌨️"), 86: ("Snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm + hail", "⛈️"), 99: ("Thunderstorm + hail", "⛈️"),
}


def describe(code: int | None) -> tuple[str, str]:
    return _WMO.get(code, ("Unknown", "❓"))


@dataclass
class GeoResult:
    name: str
    lat: float
    lon: float
    country: str = ""


_cache: dict[tuple[float, float], tuple[float, dict]] = {}


def geocode(name: str) -> GeoResult | None:
    params = {"name": name, "count": 1, "language": "en", "format": "json"}
    r = httpx.get(GEOCODE_URL, params=params, timeout=10)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return None
    top = results[0]
    label = ", ".join(p for p in (top.get("name"), top.get("country")) if p)
    return GeoResult(name=label, lat=top["latitude"], lon=top["longitude"],
                     country=top.get("country", ""))


def get_weather(lat: float, lon: float) -> dict:
    key = (round(lat, 3), round(lon, 3))
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_TTL_S:
        return cached[1]

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,apparent_temperature",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 1,
    }
    r = httpx.get(FORECAST_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    cur = data.get("current", {})
    daily = data.get("daily", {})
    cur_code = cur.get("weather_code")
    day_code = (daily.get("weather_code") or [None])[0]
    cur_text, cur_emoji = describe(cur_code)
    day_text, day_emoji = describe(day_code)

    out = {
        "current": {
            "temperature_c": cur.get("temperature_2m"),
            "apparent_c": cur.get("apparent_temperature"),
            "humidity_pct": cur.get("relative_humidity_2m"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "code": cur_code,
            "text": cur_text,
            "emoji": cur_emoji,
        },
        "today": {
            "high_c": (daily.get("temperature_2m_max") or [None])[0],
            "low_c": (daily.get("temperature_2m_min") or [None])[0],
            "precip_mm": (daily.get("precipitation_sum") or [None])[0],
            "precip_prob_pct": (daily.get("precipitation_probability_max") or [None])[0],
            "code": day_code,
            "text": day_text,
            "emoji": day_emoji,
        },
    }
    _cache[key] = (now, out)
    return out
