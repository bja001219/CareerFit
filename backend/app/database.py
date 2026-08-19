"""SQLAlchemy engine and session factory.

Uses SQLite (`careerfit.db`) with two runtime tweaks:

* ``PRAGMA foreign_keys=ON`` — required for ``ON DELETE CASCADE`` on
  ``fit_analyses`` to actually cascade (SPEC §8).
* Uploads directory is ensured on init so ``document_service`` never trips
  over a missing parent path when the very first upload lands.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_ROOT / "careerfit.db"
UPLOADS_ROOT = BACKEND_ROOT / "uploads"


def _sqlite_url(path: Path) -> str:
    # Windows-safe: SQLAlchemy accepts forward slashes.
    return f"sqlite:///{path.as_posix()}"


engine = create_engine(
    _sqlite_url(DB_PATH),
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _record) -> None:  # noqa: ANN001 — dialect callback
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Common declarative base for all ORM models."""


def init_db() -> None:
    """Create tables and ensure the uploads directory exists.

    Called from FastAPI lifespan.  Safe to call repeatedly.
    """
    # Import inside init_db so SQLAlchemy sees model classes before create_all.
    # (models package registers subclasses with ``Base.metadata`` on import.)
    import app.models  # noqa: F401 — import for side-effect

    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    (UPLOADS_ROOT / "career" / "resume").mkdir(parents=True, exist_ok=True)
    (UPLOADS_ROOT / "career" / "career_desc").mkdir(parents=True, exist_ok=True)
    (UPLOADS_ROOT / "career" / "portfolio").mkdir(parents=True, exist_ok=True)
    (UPLOADS_ROOT / "job").mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
