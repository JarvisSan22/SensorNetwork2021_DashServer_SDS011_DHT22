"""Node-flashing + provisioning API (Phase 4 / sensor-config update).

Local-only convenience: writes prebuilt firmware to an ESP32 plugged into the
server's USB, then (optionally) pushes its WiFi + sensor config over the same
USB cable so the node boots ready. Captive portal remains as a fallback.
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel

from .. import config
from ..services import flasher

router = APIRouter(prefix="/api/flash", tags=["flash"])

# Wiring shown by the dashboard "Show pin setup" modal — must match the firmware.
PIN_SETUP = {
    "dht": {
        "name": "DHT22 (temperature + humidity)",
        "pins": [["VCC", "3V3"], ["GND", "GND"], ["DATA", "GPIO 4"],
                 ["pull-up", "10kΩ between DATA and VCC"]],
    },
    "pms": {
        "name": "PMS5003 (PM2.5 + PM10)",
        "pins": [["VCC", "5V"], ["GND", "GND"], ["TX", "GPIO 16 (RX2)"], ["RX", "GPIO 17 (TX2)"]],
    },
    "bmp": {
        "name": "BMP280 (pressure)",
        "pins": [["VCC", "3V3"], ["GND", "GND"], ["SDA", "GPIO 21"], ["SCL", "GPIO 22"],
                 ["I2C addr", "0x76"]],
    },
}


@router.get("")
def flash_status() -> dict:
    """Detected serial ports, available firmware, and the pin-setup reference."""
    return {
        "ports": [p.__dict__ for p in flasher.list_serial_ports()],
        "firmware": flasher.available_firmware(),
        "pin_setup": PIN_SETUP,
        "defaults": {
            "wifi_ssid": config.DEFAULT_WIFI_SSID,
            "wifi_pass": config.DEFAULT_WIFI_PASS,
            "server_url": config.DEFAULT_SERVER_URL,
        },
    }


class Sensors(BaseModel):
    dht: bool = True
    pms: bool = False
    bmp: bool = False
    sds: bool = False


class FlashRequest(BaseModel):
    port: str
    variant: str = "combo_node"
    baud: int = 460800
    # Provisioning (auto serial). Skipped if provision=False or no wifi_ssid.
    provision: bool = True
    wifi_ssid: str | None = None
    wifi_pass: str | None = None
    server_url: str | None = None
    node: str | None = None
    placement: str = "indoor"
    sensors: Sensors = Sensors()


class MonitorRequest(BaseModel):
    port: str
    seconds: int = 15
    # 115200 = firmware output; 74880 = ESP8266 boot-ROM banner / reset reason.
    baud: int = 115200


@router.post("/monitor")
def monitor(req: MonitorRequest) -> dict:
    """Capture serial output from a connected node so the UI can show it live-ish."""
    return flasher.read_serial(req.port, baud=req.baud, seconds=min(max(req.seconds, 1), 60))


@router.post("")
def do_flash(req: FlashRequest) -> dict:
    flash_res = flasher.flash(req.port, req.variant, baud=req.baud)
    out: dict = {"flash": flash_res, "provision": None}

    if not flash_res["ok"]:
        return out
    if not (req.provision and req.wifi_ssid):
        out["provision"] = {"ok": False, "error": "skipped (no WiFi / provision off — use captive portal)", "log": ""}
        return out

    # Give the board a moment to reboot into the firmware before provisioning.
    time.sleep(3)
    config = {
        "wifi_ssid": req.wifi_ssid,
        "wifi_pass": req.wifi_pass or "",
        "server": req.server_url or "",
        "node": req.node or "",
        "placement": req.placement,
        "dht": req.sensors.dht,
        "pms": req.sensors.pms,
        "bmp": req.sensors.bmp,
        "sds": req.sensors.sds,
    }
    out["provision"] = flasher.provision_serial(req.port, config)
    return out
