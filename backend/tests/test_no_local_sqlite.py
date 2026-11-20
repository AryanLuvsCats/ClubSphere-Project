"""Guards the rule that user data is stored only in the remote (Neon) database.

A local, file-based SQLite database must never be used by the application, so a
misconfigured ``DATABASE_URL`` fails fast at startup instead of silently writing
users to a file on disk. In-memory SQLite stays available for the test suite.
"""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(database_url: str) -> Settings:
    return Settings(
        ENVIRONMENT="development",
        DEBUG=True,
        DATABASE_URL=database_url,
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


def test_neon_postgres_url_is_allowed():
    url = "postgresql://neondb_owner:npg_secret@ep-sparkling-frog-az3kakj8-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require"
    assert _settings(url).DATABASE_URL == url


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
