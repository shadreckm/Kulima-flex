"""Database connection factory for SQLite and Supabase Postgres.

This module provides a unified interface for database connections that can
switch between SQLite (local development) and Supabase Postgres (production)
via a feature flag.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Union

from kulima.config import get_settings

_log = logging.getLogger(__name__)

# Lazy import SQLAlchemy for Supabase (only when needed)
_sqlalchemy_available = False
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker, Session
    _sqlalchemy_available = True
except ImportError:
    _log.debug("SQLAlchemy not available - Supabase mode disabled")


settings = get_settings()


class DatabaseConnection:
    """Abstract database connection interface."""

    @contextmanager
    def connect(self) -> Iterator[Union[sqlite3.Connection, Session]]:
        """Return a database connection or session."""
        raise NotImplementedError


class SQLiteConnection(DatabaseConnection):
    """SQLite connection with transaction isolation."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class SupabaseConnection(DatabaseConnection):
    """Supabase Postgres connection via SQLAlchemy."""

    def __init__(self, database_url: str):
        if not _sqlalchemy_available:
            raise RuntimeError("SQLAlchemy required for Supabase mode but not installed")
        self.engine = create_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
        self.SessionLocal = sessionmaker(bind=self.engine)

    @contextmanager
    def connect(self) -> Iterator[Session]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def get_database() -> DatabaseConnection:
    """Factory function returning appropriate connection based on config.

    Returns:
        SQLiteConnection if USE_SUPABASE is false or DATABASE_URL not set
        SupabaseConnection if USE_SUPABASE is true and DATABASE_URL is set
    """
    if settings.use_supabase and settings.database_url:
        _log.info("Using Supabase Postgres connection")
        return SupabaseConnection(settings.database_url)
    _log.info("Using SQLite connection at: %s", settings.db_path)
    return SQLiteConnection(settings.db_path)


def is_supabase_mode() -> bool:
    """Check if running in Supabase mode."""
    return settings.use_supabase and bool(settings.database_url)


def get_database_type() -> str:
    """Get the current database type identifier."""
    return "supabase" if is_supabase_mode() else "sqlite"
