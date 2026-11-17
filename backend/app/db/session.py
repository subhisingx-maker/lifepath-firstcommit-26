from __future__ import annotations

from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401  (registers the tables)

_engine: Optional[Engine] = None
_factory: Optional[sessionmaker] = None


def make_engine(url: str) -> Engine:
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_connection, _):          # SQLite ignores foreign keys unless asked
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
    return engine


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        _engine = make_engine(get_settings().database_url)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def init_db(engine: Optional[Engine] = None) -> None:
    """Create tables if missing. Alembic migrations replace this once the schema settles (see CHECKLIST)."""
    Base.metadata.create_all(engine or get_engine())


def get_db() -> Iterator[Session]:
    get_engine()
    assert _factory is not None
    db = _factory()
    try:
        yield db
    finally:
        db.close()
