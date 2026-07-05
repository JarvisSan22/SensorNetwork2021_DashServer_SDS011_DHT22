# Firmware (ESP8266 / ESP32 nodes)

PlatformIO projects for the sensor nodes. Built in **Phase 4** of the plan.

Planned variants:

| Project | Sensors | Sends |
|---------|---------|-------|
| `dht22_node/` | DHT22 | temperature, humidity |
| `sds011_node/` | SDS011 | PM2.5, PM10 |
| `combo_node/` | DHT22 + SDS011 | all of the above |

Design (see [`../Docs/MODERNIZATION_PLAN.md`](../Docs/MODERNIZATION_PLAN.md) §2, §6):

- WiFi + server URL + token entered via a **WiFiManager captive portal** on first
  boot — no credentials compiled into source.
- Data sent as `POST /api/ingest` JSON (replaces the old GET-in-URL firmware).
- Compiled binaries land in `prebuilt/` for the dashboard's "Add Node" flasher.

This folder is a placeholder until Phase 4.
