"""Local sensor collector.

Reads sensors wired directly to the home-server box and POSTs to the same
/api/ingest endpoint the ESP32 nodes use, so there is a single ingestion path.
Run as a standalone process (see run.py / README).
"""
