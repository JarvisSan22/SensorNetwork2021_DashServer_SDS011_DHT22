"""Database engine + session (SQLModel/SQLite)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import DATABASE_URL

# check_same_thread=False so the rollup scheduler thread can share the engine.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create tables if they don't exist."""
    # Importing models registers them on SQLModel.metadata.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a DB session."""
    with Session(engine) as session:
        yield session


def ping() -> bool:
    """Liveness check used by /health."""
    from sqlalchemy import text

    with Session(engine) as session:
        session.exec(text("SELECT 1"))
    return True
