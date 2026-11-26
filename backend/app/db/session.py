"""SQLAlchemy engine and session management for Azure SQL Database, PostgreSQL, and in-memory SQLite."""

from typing import Generator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine, event, func, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings


def is_mssql_url(raw_url: str) -> bool:
    """Return True if the database URL targets Microsoft SQL Server / Azure SQL Database."""
    lower = (raw_url or "").strip().lower()
    return lower.startswith(("mssql://", "mssql+"))


def _ensure_mssql_query_defaults(raw_url: str) -> str:
    """Ensure clean Azure SQL driver query params without leaking Postgres-only parameters."""
    parts = urlsplit(raw_url)
    scheme_lower = parts.scheme.lower()
    raw_pairs = parse_qsl(parts.query, keep_blank_values=True)

    # Strip PostgreSQL-only params that break pyodbc / pymssql connectors.
    postgres_only = {"sslmode", "channel_binding", "sslrootcert"}
    query_pairs = [(k, v) for k, v in raw_pairs if k.lower() not in postgres_only]

    if scheme_lower == "mssql+pymssql":
        # pymssql rejects ODBC driver/Encrypt/TrustServerCertificate query kwargs cleanly via URL.
        odbc_only = {"driver", "encrypt", "trustservercertificate", "odbc_options"}
        query_pairs = [(k, v) for k, v in query_pairs if k.lower() not in odbc_only]
    elif scheme_lower in {"mssql+pyodbc", "mssql+aioodbc"}:
        keys_lower = {k.lower() for k, _ in query_pairs}
        if "driver" not in keys_lower:
            query_pairs.append(("driver", settings.AZURE_SQL_DRIVER))
        if "encrypt" not in keys_lower:
            query_pairs.append(("Encrypt", settings.AZURE_SQL_ENCRYPT))
        if "trustservercertificate" not in keys_lower:
            query_pairs.append(("TrustServerCertificate", settings.AZURE_SQL_TRUST_SERVER_CERTIFICATE))

    encoded_query = urlencode(query_pairs)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, encoded_query, parts.fragment))


def normalize_sync_database_url(raw_url: str) -> str:
    """Normalize DATABASE_URL into a synchronous SQLAlchemy driver URL.

    Converts ``postgres://`` / bare ``postgresql://`` -> ``postgresql+psycopg://``
    (matching our installed ``psycopg`` v3 driver) and ``mssql://`` /
    ``mssql+aioodbc://`` -> ``mssql+pyodbc://`` with Azure SQL ODBC defaults.
    """
    url = (raw_url or "").strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif url.startswith("mssql+aioodbc://"):
        url = url.replace("mssql+aioodbc://", "mssql+pyodbc://", 1)
    elif url.startswith("mssql://"):
        url = url.replace("mssql://", "mssql+pyodbc://", 1)

    if is_mssql_url(url):
        url = _ensure_mssql_query_defaults(url)
    return url


def normalize_async_database_url(raw_url: str) -> str:
    """Normalize an Azure SQL URL into an ``mssql+aioodbc://`` async URL."""
    url = (raw_url or "").strip()
    if url.startswith("mssql+pyodbc://"):
        url = url.replace("mssql+pyodbc://", "mssql+aioodbc://", 1)
    elif url.startswith("mssql://"):
        url = url.replace("mssql://", "mssql+aioodbc://", 1)
    if url.lower().startswith("mssql+aioodbc://"):
        url = _ensure_mssql_query_defaults(url)
    return url


def create_configured_engine(raw_url: str) -> Engine:
    """Create a SQLAlchemy Engine tuned for Azure SQL Database, PostgreSQL, or test SQLite."""
    sync_url = normalize_sync_database_url(raw_url)
    connect_args: dict = {}

    if sync_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        db_engine = create_engine(
            sync_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )

        @event.listens_for(db_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return db_engine

    if is_mssql_url(sync_url):
        engine_kwargs: dict = {
            "pool_pre_ping": True,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
        }
        if "+pymssql" in sync_url.lower():
            connect_args["login_timeout"] = settings.DB_CONNECT_TIMEOUT
            connect_args["timeout"] = settings.DB_CONNECT_TIMEOUT
        else:
            connect_args["timeout"] = settings.DB_CONNECT_TIMEOUT
            engine_kwargs["fast_executemany"] = True

        return create_engine(sync_url, connect_args=connect_args, **engine_kwargs)

    # PostgreSQL configuration (Neon / Azure Flexible Server fallback)
    connect_args["connect_timeout"] = settings.DB_CONNECT_TIMEOUT
    if getattr(settings, "AZURE_POSTGRES_SSLROOTCERT", None):
        connect_args["sslrootcert"] = settings.AZURE_POSTGRES_SSLROOTCERT

    return create_engine(
        sync_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
    )


engine = create_configured_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health(db: Session) -> bool:
    """Verifies that the database is reachable and accepting queries."""
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def close_db_connections() -> None:
    """Closes the database connection pool cleanly on application shutdown."""
    try:
        engine.dispose()
    except Exception:
        pass


def escape_like(query_str: str) -> str:
    """Escapes SQL LIKE wildcards (%, _, \\) to prevent LIKE injection."""
    return (
        query_str.strip()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def case_insensitive_like(column, pattern: str):
    """Cross-dialect case-insensitive LIKE replacing Postgres-specific ILIKE."""
    return func.lower(column).like(func.lower(pattern), escape="\\")


def case_insensitive_equals(column, value: str):
    """Cross-dialect case-insensitive exact match replacing ILIKE without wildcards."""
    return func.lower(column) == func.lower(value)
