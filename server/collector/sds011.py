"""SDS011 particulate sensor driver (USB serial).

Modernized from the legacy AQ_run/Scripts/sds_rec.py (Python 2 byte-strings ->
Python 3 bytes). The SDS011 in active-reporting mode (factory default) streams
10-byte frames at 9600 baud:

    AA C0 PM25_L PM25_H PM10_L PM10_H ID1 ID2 CHECKSUM AB

PM2.5 = (PM25_L | PM25_H<<8) / 10   (µg/m³), likewise PM10.
CHECKSUM = sum(data bytes 2..7) & 0xFF.
"""

from __future__ import annotations

import time

HEAD = 0xAA
TAIL = 0xAB
CMD_REPLY = 0xC0
FRAME_LEN = 10


def parse_frame(frame: bytes) -> tuple[float, float] | None:
    """Validate a 10-byte frame and return (pm25, pm10), or None if invalid."""
    if len(frame) != FRAME_LEN or frame[0] != HEAD or frame[-1] != TAIL:
        return None
    if frame[1] != CMD_REPLY:
        return None
    if (sum(frame[2:8]) & 0xFF) != frame[8]:
        return None
    pm25 = (frame[2] | (frame[3] << 8)) / 10.0
    pm10 = (frame[4] | (frame[5] << 8)) / 10.0
    return pm25, pm10


class SDS011:
    """Reads PM2.5 / PM10 from an SDS011 on a serial port."""

    def __init__(self, port: str, baud: int = 9600, timeout: float = 2.0) -> None:
        import serial  # imported here so the module loads without pyserial present

        self.ser = serial.Serial(port, baud, timeout=timeout)

    def read_once(self, max_wait: float = 3.0) -> tuple[float, float] | None:
        """Block until a valid frame arrives (or max_wait elapses)."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            if self.ser.read(1) != bytes([HEAD]):
                continue
            rest = self.ser.read(FRAME_LEN - 1)
            frame = bytes([HEAD]) + rest
            parsed = parse_frame(frame)
            if parsed is not None:
                return parsed
        return None

    def read_average(self, samples: int = 5, max_wait: float = 10.0) -> tuple[float, float] | None:
        """Average several frames to smooth the noisy per-frame values."""
        pm25s, pm10s = [], []
        deadline = time.time() + max_wait
        while len(pm25s) < samples and time.time() < deadline:
            r = self.read_once(max_wait=max_wait)
            if r:
                pm25s.append(r[0])
                pm10s.append(r[1])
        if not pm25s:
            return None
        return round(sum(pm25s) / len(pm25s), 1), round(sum(pm10s) / len(pm10s), 1)

    def close(self) -> None:
        try:
            self.ser.close()
        except Exception:
            pass
