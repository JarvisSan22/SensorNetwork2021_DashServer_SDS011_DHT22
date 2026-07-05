#!/usr/bin/env bash
#
# Native (no-Docker) install for the SensorNet server.
# Creates a venv, installs the app, seeds server/.env, and — if systemd is
# present — installs + starts a service. Re-runnable (idempotent).
#
#   ./deploy/install-native.sh
#
# Update later with:  git pull && ./deploy/install-native.sh && sudo systemctl restart sensornet
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_DIR="$REPO_ROOT/server"
VENV="$SERVER_DIR/.venv"
# The service runs as the invoking user (not root) so it can reach USB + the repo.
SERVICE_USER="${SUDO_USER:-$USER}"

echo "==> Repo:    $REPO_ROOT"
echo "==> Server:  $SERVER_DIR"
echo "==> Venv:    $VENV"
echo "==> User:    $SERVICE_USER"

echo "==> Creating/refreshing virtualenv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
echo "==> Installing app + dependencies"
"$VENV/bin/pip" install --quiet -e "$SERVER_DIR"

if [ ! -f "$SERVER_DIR/.env" ]; then
  cp "$SERVER_DIR/.env.example" "$SERVER_DIR/.env"
  echo "==> Created $SERVER_DIR/.env — edit your WiFi/server values."
fi

# Ensure the service user can open USB serial ports for the flashing wizard.
if getent group dialout >/dev/null 2>&1 && ! id -nG "$SERVICE_USER" | grep -qw dialout; then
  echo "==> Adding $SERVICE_USER to 'dialout' (USB serial). Re-login for it to take effect."
  sudo usermod -aG dialout "$SERVICE_USER" || true
fi

if command -v systemctl >/dev/null 2>&1; then
  UNIT=/etc/systemd/system/sensornet.service
  echo "==> Installing systemd unit -> $UNIT (sudo)"
  sed -e "s|__USER__|$SERVICE_USER|g" \
      -e "s|__SERVER_DIR__|$SERVER_DIR|g" \
      -e "s|__VENV__|$VENV|g" \
      "$SCRIPT_DIR/sensornet.service" | sudo tee "$UNIT" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable --now sensornet
  echo "==> Service started. Check it with:  systemctl status sensornet"
else
  echo "==> systemd not found. Run it manually:"
  echo "    cd $SERVER_DIR && $VENV/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"
fi

echo "==> Done. Dashboard: http://<this-host>:8000/"
