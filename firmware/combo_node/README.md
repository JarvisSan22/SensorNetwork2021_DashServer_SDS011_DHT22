# Configurable node firmware (ESP32 + ESP8266)

**One firmware for every node.** All sensor drivers are compiled in; which run
is chosen per-node at provisioning. Sends `POST /api/ingest`. The same source
builds for **ESP32** (`env:esp32dev`) and **ESP8266** (`env:esp8266`, e.g.
NodeMCU/Wemos) — the pins differ per chip, see the table.

Supported sensors (toggle in the dashboard's *Add a node*):

| Sensor | Metrics | ESP32 pins | ESP8266 pins (NodeMCU) |
|--------|---------|-----------|------------------------|
| **DHT22** | temperature, humidity | DATA → GPIO 4 | DATA → GPIO 14 (D5) — + 3V3, GND, 10k pull-up |
| **PMS5003** | PM2.5, PM10 | TX → GPIO 16 (RX2), RX → GPIO 17 (TX2) | TX → GPIO 12 (D6), RX → GPIO 13 (D7) — 5V, GND |
| **BMP280** | pressure | SDA → GPIO 21, SCL → GPIO 22 | SDA → GPIO 4 (D2), SCL → GPIO 5 (D1) — 3V3, GND, I2C 0x76 |
| SDS011 (alt PM) | PM2.5, PM10 | shares the PMS5003 UART pins | shares the PMS5003 pins (SoftwareSerial) |

> **ESP8266 notes:** it has no second hardware UART, so the PM sensor is read
> over `SoftwareSerial`; and no NVS, so the node config is stored on LittleFS
> instead of `Preferences`. Both are handled automatically by `#ifdef ESP8266`.

## Provisioning (two paths)

1. **Auto serial (primary):** an unprovisioned node prints `AWAITING_CONFIG` on
   USB serial. The dashboard's *Add a node → Flash & configure* writes the
   firmware, then pushes a one-line JSON config (WiFi + server + node + sensor
   toggles) over the same cable. The node saves it to NVS and boots connected.
2. **Captive portal (fallback):** if no serial config arrives (or you hold the
   **BOOT** button at power-on), it opens the `SensorNet-Setup` WiFi AP for
   manual secd firmware/combo_nodetup. Use this to re-provision a node in the field.

## Build

```bash
# Install PlatformIO core once. The COMMAND is `pio`, but the PACKAGE is
# `platformio` — do NOT `pip install pio` (that's an unrelated broken package
# that fails with "No module named 'requirements'").
#   pip install platformio esptool          # into the server's venv, or:
#   pipx install platformio esptool         # isolated (recommended on Pi/Debian)
cd firmware/combo_node
pio run                          # compile BOTH envs (esp32dev + esp8266)
pio run -e esp32dev -t upload    # flash an ESP32 connected to THIS machine
pio run -e esp8266  -t upload    # flash an ESP8266 (NodeMCU/Wemos)
pio device monitor               # watch serial output
```

## Build the binaries for the dashboard flasher

The server-side flasher writes a single image at offset `0x0`. It picks
`--chip` from the file name (`*_esp8266` → esp8266, else esp32), so name the
outputs exactly as below.

**ESP32** — needs the merged image (bootloader + partitions + app):

```bash
cd firmware/combo_node
pio run -e esp32dev
esptool --chip esp32 merge_bin -o ../prebuilt/combo_node.bin \
    0x1000  .pio/build/esp32dev/bootloader.bin \
    0x8000  .pio/build/esp32dev/partitions.bin \
    0x10000 .pio/build/esp32dev/firmware.bin
```

**ESP8266** — the Arduino build is already a single image at `0x0`, so just copy it:

```bash
pio run -e esp8266
cp .pio/build/esp8266/firmware.bin ../prebuilt/combo_node_esp8266.bin
```

Then **Dashboard → Add a node → Flash & configure** lists both `combo_node`
(ESP32) and `combo_node_esp8266` in the *Firmware* dropdown — pick the one that
matches the board you plugged in.

## Captive-portal fields (fallback path only)

If you provision via the `SensorNet-Setup` AP instead of auto serial, the form
asks for: **Server URL** (e.g. `http://192.168.1.50:8000`), **Node name**,
**Placement** (indoor/outdoor), and a `1/0` for each of **DHT22 / PMS5003 /
BMP280**. The node then posts every 30 s and the server auto-registers it.

Hold **BOOT** at power-on any time to force the captive portal and re-provision.
