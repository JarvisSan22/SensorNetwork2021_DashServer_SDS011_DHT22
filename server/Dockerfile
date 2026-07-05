# SensorNet home server image.
#
# Build context is the REPO ROOT (see docker-compose.yml), because the app needs
# the repo layout preserved: config.SERVER_DIR resolves to /app/server, and the
# flashing wizard looks for firmware at SERVER_DIR.parent/firmware (/app/firmware).
# So we install the package *editable* rather than into site-packages.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SENSORNET_DATA_DIR=/data \
    SENSORNET_DB_PATH=/data/sensornet.db

WORKDIR /app/server

# Install the app (and its deps) editable so the source tree stays importable
# from /app/server — keeps SERVER_DIR and the firmware/.env lookups correct.
COPY server/pyproject.toml ./
COPY server/app ./app
RUN pip install -e .

# Prebuilt firmware for the flashing wizard (repo_root/firmware -> /app/firmware).
# Usually bind-mounted fresh by compose; copied here so the image also works alone.
COPY firmware /app/firmware

# The SQLite DB lives on a mounted volume so it survives image rebuilds/updates.
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
