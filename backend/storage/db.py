"""
storage/db.py
PostgreSQL connection pool using SQLAlchemy 2.x.
Provides get_session() context manager used across all modules.
"""

import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from storage.models import Base

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://hr_user:hr_pass@localhost:5432/hr_databridge"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,          # Validates connection before use
    pool_recycle=3600,           # Recycle connections every hour
    echo=os.getenv("LOG_LEVEL") == "DEBUG",
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema ready.")


@contextmanager
def get_session() -> Session:
    """
    Context manager yielding a SQLAlchemy session.
    Automatically commits on success, rolls back on exception.

    Usage:
        with get_session() as session:
            session.add(record)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error(f"Session rolled back due to: {exc}")
        raise
    finally:
        session.close()


def health_check() -> dict:
    """Returns DB connectivity status — used by /health endpoint."""
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok", "database": DATABASE_URL.split("@")[-1]}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
