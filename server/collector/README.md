# Local collector (server-attached sensors)

For sensors wired **directly to the home-server box** rather than to a WiFi ESP32
node. It reads them and POSTs to the same `/api/ingest` endpoint, so a local
sensor shows up on the dashboard exactly like any other node.

- **SDS011 (PM2.5/PM10)** — USB serial, works on any Linux PC or Raspberry Pi.
- **DHT22 (temp/humidity)** — needs GPIO, so Raspberry Pi only; install the
  `dht` extra. Skipped gracefully where there's no GPIO.

## Run

```bash
cd server
. .venv/bin/activate

# SDS011 on USB, reporting as an indoor node
python -m collector.run --node server-room --placement indoor --sds-port /dev/ttyUSB0

# + DHT22 on GPIO 4 (Raspberry Pi; needs:  pip install -e '.[dht]')
python -m collector.run --node server-room --sds-port /dev/ttyUSB0 --dht-pin 4

# Try it with no hardware (synthesizes readings)
python -m collector.run --node test-collector --simulate --once
```

Key flags: `--server` (default `http://localhost:8000`), `--interval` (default 30s),
`--once`, `--dry-run` (print, don't POST), `--simulate` (fake readings).

## Run it as a service

A systemd unit keeps it running on boot (deployment details land in Phase 6):

```ini
# /etc/systemd/system/sensornet-collector.service
[Unit]
Description=SensorNet local collector
After=network-online.target sensornet.service

[Service]
WorkingDirectory=/opt/sensornet/server
ExecStart=/opt/sensornet/server/.venv/bin/python -m collector.run \
    --node server-room --sds-port /dev/ttyUSB0 --placement indoor
Restart=always

[Install]
WantedBy=multi-user.target
```

The collecting user needs serial access: `sudo usermod -aG dialout $USER`.
