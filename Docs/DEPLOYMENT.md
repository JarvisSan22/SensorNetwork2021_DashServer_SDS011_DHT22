# Deployment

Two ways to run SensorNet on a new server. Both keep **your data separate from
the app code**, so updating the code never risks the database.

- **Docker** — reproducible, clean version-controlled updates/rollback. USB
  flashing needs extra config (Docker doesn't hot-plug USB cleanly).
- **Native (systemd)** — runs directly on the host. Simplest for the ESP32
  **flashing wizard** and any USB/GPIO sensors, since the process sees the
  devices directly.

> If this box flashes ESP32 nodes over USB, **native is smoother**. Docker is the
> better pick for a pure ingest+dashboard server. You can run both and compare.

See [APP_ARCHITECTURE.md](APP_ARCHITECTURE.md) for how the app itself is wired.

---

## Option A — Docker

### Files
- `server/Dockerfile` — the image (editable install so `firmware/` + `.env`
  lookups keep working).
- `docker-compose.yml` (repo root) — service, ports, data volume, USB notes.
- `.dockerignore`.

### One-time setup
```bash
# Let your user run docker without sudo (then log out / back in):
sudo usermod -aG docker "$USER"

cp server/.env.example server/.env   # optional: WiFi/server defaults
```

### Run
```bash
docker compose up -d --build         # build + start in background
docker compose logs -f               # watch logs
# Dashboard: http://<this-host>:8000/
```

### Your data (the whole point)
The SQLite DB lives in the named volume **`sensornet-data`**, mounted at `/data`
inside the container — never inside the image. Rebuilding/updating the image
leaves it untouched.

```bash
docker volume inspect sensornet_sensornet-data          # where it is on disk
# Back up:
docker run --rm -v sensornet_sensornet-data:/d -v "$PWD":/b busybox \
    cp /d/sensornet.db /b/sensornet-backup.db
```
Prefer a folder you can browse directly? Swap the volume line in
`docker-compose.yml` for a bind mount: `- ./server/data:/data`.

### Updating (version control)
```bash
git pull
docker compose up -d --build         # rebuild app; data volume persists
```
Tag releases (`docker tag sensornet-server:latest sensornet:v0.1.0`) if you want
easy rollback to a previous image.

### Flashing ESP32s from Docker
Docker can't cleanly hot-plug USB, so flashing is **off by default** (the server
still runs). To flash, uncomment ONE block in `docker-compose.yml` and
`docker compose up -d`:
- **A) specific adapter** — `devices: ["/dev/ttyUSB0:/dev/ttyUSB0"]` +
  `group_add: [dialout]`. The adapter must be plugged in when the container starts.
- **B) dynamic ports** — `privileged: true` + `- /dev:/dev`. Simplest, broad
  privileges. Handles port names that change between plug-ins.

Firmware images are bind-mounted from `./firmware`, so rebuilding firmware on the
host is picked up without rebuilding the image.

---

## Option B — Native (systemd + venv)

### Files
- `deploy/install-native.sh` — creates the venv, installs the app, seeds
  `server/.env`, adds you to `dialout`, installs + starts the systemd service.
- `deploy/sensornet.service` — the unit template (paths filled in on install).

### Run
```bash
./deploy/install-native.sh
# Dashboard: http://<this-host>:8000/
```
Requires `python3` (>=3.11) and `sudo` for the systemd step. The service runs as
your user (so it can reach USB + the repo), restarts on failure, and starts on boot.

### Manage
```bash
systemctl status sensornet
journalctl -u sensornet -f            # logs
sudo systemctl restart sensornet
```

### Your data
Default DB path is `server/data/sensornet.db` (gitignored). To put it on a
separate disk/mount, set `SENSORNET_DB_PATH` (and `SENSORNET_DATA_DIR`) in
`server/.env`, e.g. `SENSORNET_DB_PATH=/var/lib/sensornet/sensornet.db`.

### Updating (version control)
```bash
git pull
./deploy/install-native.sh           # refresh deps (editable, so code is already live)
sudo systemctl restart sensornet
```

### Flashing ESP32s
Works out of the box — the service has the `dialout` group and the process opens
`/dev/ttyUSB*` directly. Just plug in a node and use the Add-a-node wizard.

---

## Which to choose

| | Docker | Native (systemd) |
|---|---|---|
| Reproducible / rollback | ★★★ | ★★ |
| ESP32 USB flashing | needs passthrough | direct ★★★ |
| Local GPIO sensor collector | needs passthrough | direct ★★★ |
| Update flow | `git pull && compose up --build` | `git pull && install-native.sh && restart` |
| Data isolation | named volume | `SENSORNET_DB_PATH` |

Both read the same `server/.env` and expose the same dashboard on port 8000.
