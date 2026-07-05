"""Server-side ESP32 / ESP8266 flashing via esptool.

Lists USB serial ports and writes a prebuilt firmware image to a plugged-in
board. The target chip is inferred from the image name (see `chip_for`), so both
`combo_node` (ESP32) and `combo_node_esp8266` flash through the same path.
Provisioning (WiFi/server/name) happens afterwards over serial (or the device's
captive portal), so flashing only needs to write the binary.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from serial.tools import list_ports

from ..config import SERVER_DIR

# firmware/prebuilt/*.bin lives next to the server dir (repo_root/firmware).
PREBUILT_DIR = SERVER_DIR.parent / "firmware" / "prebuilt"

# USB-serial bridges commonly found on ESP32 dev boards.
_ESP_HINTS = ("CP210", "CH340", "CH910", "FT231", "FTDI", "USB JTAG", "Silicon Labs")


@dataclass
class Port:
    device: str
    description: str
    likely_esp: bool


def list_serial_ports() -> list[Port]:
    """USB serial ports only — built-in ttyS*/COM ports (no USB VID) are noise."""
    out: list[Port] = []
    for p in list_ports.comports():
        if p.vid is None:  # not a USB device (e.g. motherboard ttyS0..31)
            continue
        blob = f"{p.description} {p.manufacturer or ''} {p.product or ''}"
        likely = any(h.lower() in blob.lower() for h in _ESP_HINTS)
        out.append(Port(device=p.device, description=p.description or p.device, likely_esp=likely))
    # Likely-ESP devices first.
    out.sort(key=lambda x: not x.likely_esp)
    return out


def available_firmware() -> list[str]:
    if not PREBUILT_DIR.exists():
        return []
    return sorted(f.stem for f in PREBUILT_DIR.glob("*.bin"))


def firmware_path(variant: str) -> Path:
    return PREBUILT_DIR / f"{variant}.bin"


def chip_for(variant: str) -> str:
    """Which esptool chip a prebuilt image targets, inferred from its name.

    `combo_node_esp8266` -> esp8266; everything else -> esp32. Passing the chip
    explicitly (rather than auto-detecting) makes esptool refuse to write an
    ESP8266 image to an ESP32 board and vice-versa, instead of bricking it.
    """
    return "esp8266" if variant.endswith("esp8266") else "esp32"


def flash(port: str, variant: str, baud: int = 460800, timeout: int = 180) -> dict:
    """Write a merged firmware image to `port`. Returns success + esptool log."""
    fw = firmware_path(variant)
    if not fw.exists():
        return {
            "ok": False,
            "error": f"firmware '{variant}' not built — see firmware/combo_node/README.md",
            "log": "",
        }

    cmd = [
        sys.executable, "-m", "esptool",
        "--chip", chip_for(variant), "--port", port, "--baud", str(baud),
        "write-flash", "0x0", str(fw),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "esptool timed out", "log": ""}
    except FileNotFoundError as exc:
        return {"ok": False, "error": f"esptool not available: {exc}", "log": ""}

    log = (proc.stdout or "") + (proc.stderr or "")
    return {"ok": proc.returncode == 0, "error": None if proc.returncode == 0 else "flash failed", "log": log}


def read_serial(port: str, baud: int = 115200, seconds: int = 15) -> dict:
    """Capture serial output from a connected node for `seconds`.

    Used by the dashboard's "Show serial" button to see what a freshly flashed
    node is doing over USB (boot log, WiFi state, AWAITING_CONFIG, crashes).
    Listens passively — it does not pulse DTR/RTS, since that reset sequence is
    adapter-specific and can drop some boards into download mode. To capture a
    fresh boot, just replug the board (or press its EN button) then read.
    """
    import time

    import serial

    lines: list[str] = []
    try:
        with serial.Serial(port, baud, timeout=1) as ser:
            # Stop the OS pulsing DTR/RTS when the port closes (HUPCL): on some
            # USB-serial adapters that pulse drops the ESP32 into download mode
            # ("waiting for download") and leaves the node not running.
            try:
                import termios

                attrs = termios.tcgetattr(ser.fileno())
                attrs[2] &= ~termios.HUPCL
                termios.tcsetattr(ser.fileno(), termios.TCSANOW, attrs)
            except Exception:
                pass

            deadline = time.time() + seconds
            while time.time() < deadline:
                raw = ser.readline().decode(errors="replace").rstrip()
                if raw:
                    lines.append(raw)
        return {
            "ok": True,
            "log": "\n".join(lines) or f"(no serial output in {seconds}s — is the board powered/printing?)",
        }
    except Exception as exc:
        return {"ok": False, "error": f"serial read failed: {exc}", "log": "\n".join(lines)}


def provision_serial(port: str, config: dict, baud: int = 115200, timeout: int = 25) -> dict:
    """Push a one-line JSON config to a freshly flashed node over USB serial.

    The firmware prints 'AWAITING_CONFIG' when unprovisioned; we wait for that
    marker, send the JSON line, and confirm on 'CONFIG_SAVED'.
    """
    import json

    import serial

    line = (json.dumps(config) + "\n").encode()
    log: list[str] = []
    try:
        with serial.Serial(port, baud, timeout=1) as ser:
            import time

            deadline = time.time() + timeout
            sent = False
            while time.time() < deadline:
                raw = ser.readline().decode(errors="replace").strip()
                if raw:
                    log.append(raw)
                if not sent and "AWAITING_CONFIG" in raw:
                    ser.write(line)
                    ser.flush()
                    sent = True
                if "CONFIG_SAVED" in raw:
                    return {"ok": True, "log": "\n".join(log)}
            return {
                "ok": False,
                "error": "no AWAITING_CONFIG from device" if not sent else "no CONFIG_SAVED confirmation",
                "log": "\n".join(log) or "(no serial output)",
            }
    except Exception as exc:
        return {"ok": False, "error": f"serial provisioning failed: {exc}", "log": "\n".join(log)}
