"""Database engine and session management (SQLAlchemy 2.0, SQLite WAL)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import config

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):  # noqa: ANN001
    if config.DATABASE_URL.startswith("sqlite"):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.utcnow()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
