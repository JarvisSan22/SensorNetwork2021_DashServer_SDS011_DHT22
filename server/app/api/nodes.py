"""Node listing, current-state summary, and metadata editing."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select

from ..db import get_session
from ..models import Metric, Node, Placement, ReadingRaw
from ..timeutils import utcnow
from .schemas import MetricReading, NodeSummary

router = APIRouter(prefix="/api", tags=["nodes"])


def _is_online(node: Node, now: datetime) -> bool:
    if node.last_seen is None:
        return False
    grace = max(3 * node.report_interval_s, 120)
    return node.last_seen >= now - timedelta(seconds=grace)


def _latest_readings(session: Session, node_id: str) -> list[MetricReading]:
    """Most recent raw value per metric for a node."""
    out: list[MetricReading] = []
    for metric in Metric:
        row = session.exec(
            select(ReadingRaw)
            .where(ReadingRaw.node_id == node_id, ReadingRaw.metric == metric)
            .order_by(ReadingRaw.ts.desc())
            .limit(1)
        ).first()
        if row is not None:
            out.append(MetricReading(metric=metric, value=row.value, ts=row.ts))
    return out


@router.get("/nodes", response_model=list[Node])
def list_nodes(session: Session = Depends(get_session)) -> list[Node]:
    return session.exec(select(Node).order_by(Node.placement, Node.name)).all()


@router.get("/summary", response_model=list[NodeSummary])
def summary(session: Session = Depends(get_session)) -> list[NodeSummary]:
    """Everything the dashboard 'Now' view needs, grouped client-side."""
    now = utcnow()
    nodes = session.exec(select(Node).order_by(Node.placement, Node.name)).all()
    return [
        NodeSummary(
            id=n.id,
            name=n.name or n.id,
            placement=n.placement,
            location=n.location,
            lat=n.lat,
            lon=n.lon,
            last_seen=n.last_seen,
            online=_is_online(n, now),
            latest=_latest_readings(session, n.id),
        )
        for n in nodes
    ]


class NodeUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    placement: Placement | None = None
    lat: float | None = None
    lon: float | None = None
    report_interval_s: int | None = None


@router.patch("/nodes/{node_id}", response_model=Node)
def update_node(
    node_id: str, patch: NodeUpdate, session: Session = Depends(get_session)
) -> Node:
    node = session.get(Node, node_id)
    if node is None:
        raise HTTPException(404, f"unknown node: {node_id}")
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(node, field, value)
    session.add(node)
    session.commit()
    session.refresh(node)
    return node


@router.delete("/nodes/{node_id}")
def delete_node(node_id: str, session: Session = Depends(get_session)) -> dict:
    """Remove a node and all of its stored readings (raw + 10-min rollups)."""
    node = session.get(Node, node_id)
    if node is None:
        raise HTTPException(404, f"unknown node: {node_id}")
    session.exec(text("DELETE FROM readingraw WHERE node_id = :n"), params={"n": node_id})
    session.exec(text("DELETE FROM reading10min WHERE node_id = :n"), params={"n": node_id})
    session.delete(node)
    session.commit()
    return {"ok": True, "deleted": node_id}
