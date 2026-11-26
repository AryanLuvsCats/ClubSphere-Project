"""Backward-compatible re-exports of SQLAlchemy database primitives."""

from app.db.session import (
    Base,
    SessionLocal,
    case_insensitive_equals,
    case_insensitive_like,
    check_db_health,
    close_db_connections,
    create_configured_engine,
    engine,
    escape_like,
    get_db,
    is_mssql_url,
    normalize_async_database_url,
    normalize_sync_database_url,
)

__all__ = [
    "Base",
    "SessionLocal",
    "case_insensitive_equals",
    "case_insensitive_like",
    "check_db_health",
    "close_db_connections",
    "create_configured_engine",
    "engine",
    "escape_like",
    "get_db",
    "is_mssql_url",
    "normalize_async_database_url",
    "normalize_sync_database_url",
]
