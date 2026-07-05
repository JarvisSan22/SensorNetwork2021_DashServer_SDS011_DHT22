"""Optional DHT22 reader for a server with GPIO (e.g. Raspberry Pi).

Uses adafruit-circuitpython-dht (install via the `dht` extra). On a generic
x86 server with no GPIO this import fails — that's fine; the collector just
skips DHT and logs a note. SDS011 (USB) still works everywhere.
"""

from __future__ import annotations


class DHTUnavailable(RuntimeError):
    pass


def read_dht(pin: int) -> tuple[float, float]:
    """Return (temperature_c, humidity_pct). Raises DHTUnavailable if no GPIO."""
    try:
        import adafruit_dht
        import board
    except Exception as exc:  # library or board support missing
        raise DHTUnavailable(
            "DHT support not available — install the 'dht' extra on a GPIO board"
        ) from exc

    pin_obj = getattr(board, f"D{pin}", None)
    if pin_obj is None:
        raise DHTUnavailable(f"no board pin D{pin}")

    device = adafruit_dht.DHT22(pin_obj)
    try:
        temperature = device.temperature
        humidity = device.humidity
    finally:
        try:
            device.exit()
        except Exception:
            pass

    if temperature is None or humidity is None:
        raise DHTUnavailable("DHT read returned no data (transient — retry)")
    return float(temperature), float(humidity)
