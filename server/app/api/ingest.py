"""POST /api/ingest — receive readings from a node.

Replaces the old GET-in-URL receiver. Unknown nodes are auto-registered with
sensible defaults so a freshly flashed device just works; metadata can be
refined later from the Settings UI.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..db import get_session
from ..models import Node, ReadingRaw
from ..timeutils import utcnow
from .schemas import IngestPayload

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest")
def ingest(payload: IngestPayload, session: Session = Depends(get_session)) -> dict:
    now = utcnow()

    node = session.get(Node, payload.node)
    if node is None:
        node = Node(id=payload.node, name=payload.name or payload.node)
        if payload.placement is not None:
            node.placement = payload.placement
        session.add(node)

    # Refresh self-reported metadata when present.
    if payload.firmware is not None:
        node.firmware = payload.firmware
    if payload.sensor_types is not None:
        node.sensor_types = ",".join(payload.sensor_types)
    node.last_seen = now

    for metric, value in payload.readings.items():
        session.add(ReadingRaw(node_id=node.id, ts=now, metric=metric, value=value))

    session.add(node)
    session.commit()

    return {"ok": True, "node": node.id, "stored": len(payload.readings), "ts": now.isoformat()}
