from __future__ import annotations

from typing import Iterator, Optional

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401  (registers the tables)

_engine: Optional[Engine] = None
_factory: Optional[sessionmaker] = None


def make_engine(url: str) -> Engine:
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
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
    target = engine or get_engine()
    Base.metadata.create_all(target)
    # Keep legacy analyses intact but unclaimed: only newly owned records are accessible.
    if 'owner_hash' not in {column['name'] for column in inspect(target).get_columns('analyses')}:
        with target.begin() as connection:
            connection.execute(text('ALTER TABLE analyses ADD COLUMN owner_hash VARCHAR(64)'))


def get_db() -> Iterator[Session]:
    get_engine()
    assert _factory is not None
    db = _factory()
    try:
        yield db
    finally:
        db.close()
