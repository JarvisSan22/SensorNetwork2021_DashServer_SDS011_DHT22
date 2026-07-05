# Configurable node firmware (ESP32)

**One firmware for every node.** All sensor drivers are compiled in; which run
is chosen per-node at provisioning. Sends `POST /api/ingest`.

Supported sensors (toggle in the dashboard's *Add a node*):

| Sensor | Metrics | ESP32 pins |
|--------|---------|-----------|
| **DHT22** | temperature, humidity | DATA → GPIO 4 (+ 3V3, GND, 10k pull-up) |
| **PMS5003** | PM2.5, PM10 | TX → GPIO 16 (RX2), RX → GPIO 17 (TX2), 5V, GND |
| **BMP280** | pressure | SDA → GPIO 21, SCL → GPIO 22, 3V3, GND (I2C 0x76) |
| SDS011 (alt PM) | PM2.5, PM10 | shares the PMS5003 UART pins |

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
# install PlatformIO core once: pip install platformio
cd firmware/combo_node
pio run                       # compile
pio run -t upload             # flash a board connected to THIS machine
pio device monitor            # watch serial output
```

## Build the merged binary for the dashboard flasher

The server-side flasher writes a single image at offset `0x0`. Produce it with:

```bash
cd firmware/combo_node
pio run
esptool --chip esp32 merge_bin -o ../prebuilt/combo_node.bin \
    0x1000  .pio/build/esp32dev/bootloader.bin \
    0x8000  .pio/build/esp32dev/partitions.bin \
    0x10000 .pio/build/esp32dev/firmware.bin
```

Then `firmware/prebuilt/combo_node.bin` is what **Dashboard → Add a node →
Flash & configure** writes to a plugged-in ESP32.

## Captive-portal fields (fallback path only)

If you provision via the `SensorNet-Setup` AP instead of auto serial, the form
asks for: **Server URL** (e.g. `http://192.168.1.50:8000`), **Node name**,
**Placement** (indoor/outdoor), and a `1/0` for each of **DHT22 / PMS5003 /
BMP280**. The node then posts every 30 s and the server auto-registers it.

Hold **BOOT** at power-on any time to force the captive portal and re-provision.
