"""Guards the rule that user data is stored only in a remote Azure SQL / cloud database.

A local, file-based SQLite database must never be used by the application, so a
misconfigured ``DATABASE_URL`` fails fast at startup instead of silently writing
users to a file on disk. In-memory SQLite stays available for the test suite.
"""
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.db.session import normalize_async_database_url, normalize_sync_database_url


def _settings(database_url: str, unpooled: str = "") -> Settings:
    return Settings(
        ENVIRONMENT="development",
        DEBUG=True,
        DATABASE_URL=database_url,
        DATABASE_URL_UNPOOLED=unpooled,
        JWT_SECRET_KEY="a" * 32,
    )


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///./clubsphere_dev.db",
        "sqlite:///D:/e/backend/clubsphere_dev.db",
        "sqlite:///test.db",
    ],
)
def test_file_based_sqlite_is_rejected(database_url: str):
    with pytest.raises(ValidationError) as exc:
        _settings(database_url)
    assert "SQLite is disabled" in str(exc.value)


@pytest.mark.parametrize("database_url", ["sqlite://", "sqlite:///:memory:"])
def test_in_memory_sqlite_is_allowed_for_tests(database_url: str):
    assert _settings(database_url).DATABASE_URL == database_url


@pytest.mark.parametrize(
    "database_url",
    [
        "mssql+pyodbc://csadmin:Secret%40123@clubsphere.database.windows.net:1433/clubsphere?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no",
        "mssql+aioodbc://csadmin:Secret%40123@clubsphere.database.windows.net:1433/clubsphere?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no",
        "mssql+pymssql://csadmin:Secret%40123@clubsphere.database.windows.net:1433/clubsphere",
    ],
)
def test_azure_sql_urls_are_accepted(database_url: str):
    cfg = _settings(database_url, unpooled=database_url)
    assert cfg.DATABASE_URL == database_url
    assert cfg.DATABASE_URL_UNPOOLED == database_url


def test_mssql_scheme_normalization():
    cfg = _settings("mssql://csadmin:Secret@clubsphere.database.windows.net:1433/clubsphere")
    assert cfg.DATABASE_URL.startswith("mssql+pyodbc://")

    sync_url = normalize_sync_database_url(
        "mssql+aioodbc://csadmin:Secret@clubsphere.database.windows.net:1433/clubsphere"
    )
    assert sync_url.startswith("mssql+pyodbc://")
    assert "ODBC+Driver+18+for+SQL+Server" in sync_url
    assert "Encrypt=yes" in sync_url
    assert "TrustServerCertificate=no" in sync_url

    async_url = normalize_async_database_url(sync_url)
    assert async_url.startswith("mssql+aioodbc://")


def test_azure_sql_components_assemble():
    s = Settings(
        ENVIRONMENT="development",
        DEBUG=True,
        DATABASE_URL="",
        AZURE_SQL_SERVER="clubsphere-srv.database.windows.net",
        AZURE_SQL_USER="csadmin",
        AZURE_SQL_PASSWORD="MyPassword@123!",
        AZURE_SQL_DATABASE="clubsphere",
        JWT_SECRET_KEY="a" * 32,
    )
    assert s.DATABASE_URL.startswith("mssql+pyodbc://")
    assert "clubsphere-srv.database.windows.net:1433/clubsphere" in s.DATABASE_URL
    assert "MyPassword%40123%21" in s.DATABASE_URL
    assert "Encrypt=yes" in s.DATABASE_URL
    assert "TrustServerCertificate=no" in s.DATABASE_URL


def test_neon_postgres_url_is_allowed():
    url = "postgresql://neondb_owner:npg_secret@ep-sparkling-frog-az3kakj8-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require"
    assert _settings(url).DATABASE_URL == url
    assert normalize_sync_database_url(url).startswith("postgresql+psycopg://")


def test_postgres_components_assemble():
    s = Settings(
        ENVIRONMENT="development",
        DEBUG=True,
        DATABASE_URL="",
        AZURE_POSTGRES_HOST="ep-sparkling-frog-az3kakj8-pooler.c-3.ap-southeast-1.aws.neon.tech",
        AZURE_POSTGRES_USER="neondb_owner",
        AZURE_POSTGRES_PASSWORD="MyPassword@123!",
        AZURE_POSTGRES_DB="neondb",
        AZURE_POSTGRES_SSLMODE="require",
        JWT_SECRET_KEY="a" * 32,
    )
    assert "ep-sparkling-frog-az3kakj8-pooler.c-3.ap-southeast-1.aws.neon.tech:5432/neondb" in s.DATABASE_URL
    assert "sslmode=require" in s.DATABASE_URL
    assert "MyPassword%40123%21" in s.DATABASE_URL
