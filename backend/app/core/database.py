from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# Engine configuration
connect_args = {}
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

is_sqlite = db_url.startswith("sqlite")

if is_sqlite:
    connect_args["check_same_thread"] = False
    engine = create_engine(
        db_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    # Azure Database for PostgreSQL Flexible Server configuration
    # Set connect timeout so unreachable remote host fails fast
    connect_args["connect_timeout"] = settings.DB_CONNECT_TIMEOUT

    # Optional explicit root certificate path for verify-full TLS
    if getattr(settings, "AZURE_POSTGRES_SSLROOTCERT", None):
        connect_args["sslrootcert"] = settings.AZURE_POSTGRES_SSLROOTCERT

    engine = create_engine(
        db_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
    )

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
