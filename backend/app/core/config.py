import secrets
from typing import Any, List, Literal, Optional, Union

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PLACEHOLDER_SECRETS = {
    "CHANGE_THIS_TO_A_SECURE_RANDOM_SECRET_KEY_FOR_PRODUCTION",
    "dev_secret_key_clubsphere_super_secure_32_chars!",
    "temporary_development_secret_key_32_characters_long_min!",
    "changeme",
    "secret",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Later files take precedence. Workspace-root files are the fallback;
        # backend-local files override them so backend/.env stays authoritative.
        env_file=(
            "../.env",
            "../.env.local",
            "../.env.production",
            ".env",
            ".env.local",
            ".env.production",
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "ClubSphere"
    ENVIRONMENT: Literal["development", "testing", "staging", "production"] = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    # None means "enabled outside production, disabled in production".
    DOCS_ENABLED: Optional[bool] = None

    # Database
    # Neon Postgres is the primary supported data store for application data.
    # No default on purpose: a missing DATABASE_URL must fail loudly instead of
    # silently falling back to a local SQLite file that diverges from Neon.
    DATABASE_URL: str = ""
    DATABASE_URL_UNPOOLED: str = ""
    NEON_BRANCH: str = ""

    # Connection Pool Settings
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0, le=100)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1, le=300)
    DB_POOL_RECYCLE: int = Field(default=300, ge=60, le=3600)
    DB_CONNECT_TIMEOUT: int = Field(default=10, ge=1, le=60)

    # Optional / fallback database connection fields
    AZURE_POSTGRES_HOST: Optional[str] = None
    AZURE_POSTGRES_PORT: int = 5432
    AZURE_POSTGRES_USER: Optional[str] = None
    AZURE_POSTGRES_PASSWORD: Optional[str] = None
    AZURE_POSTGRES_DB: Optional[str] = None
    AZURE_POSTGRES_SSLMODE: str = "require"
    AZURE_POSTGRES_SSLROOTCERT: Optional[str] = None

    # Development convenience only. Production must run `alembic upgrade head`
    # and set AUTO_CREATE_SCHEMA=false so schema changes are tracked as migrations.
    AUTO_CREATE_SCHEMA: bool = True

    @model_validator(mode="before")
    @classmethod
    def assemble_database_url_from_components(cls, data: Any) -> Any:
        if isinstance(data, dict):
            db_url = (data.get("DATABASE_URL") or "").strip()
            if not db_url and data.get("AZURE_POSTGRES_HOST"):
                import urllib.parse
                user = urllib.parse.quote_plus(str(data.get("AZURE_POSTGRES_USER") or ""))
                password = urllib.parse.quote_plus(str(data.get("AZURE_POSTGRES_PASSWORD") or ""))
                host = data.get("AZURE_POSTGRES_HOST")
                port = data.get("AZURE_POSTGRES_PORT", 5432)
                dbname = data.get("AZURE_POSTGRES_DB", "clubsphere")
                sslmode = data.get("AZURE_POSTGRES_SSLMODE", "require")
                
                auth_part = f"{user}:{password}@" if user or password else ""
                assembled_url = f"postgresql+psycopg://{auth_part}{host}:{port}/{dbname}?sslmode={sslmode}"
                rootcert = data.get("AZURE_POSTGRES_SSLROOTCERT")
                if rootcert:
                    assembled_url += f"&sslrootcert={urllib.parse.quote_plus(str(rootcert))}"
                data["DATABASE_URL"] = assembled_url
        return data

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        url = (v or "").strip()
        if not url:
            raise ValueError(
                "DATABASE_URL is not set. Set it to your Neon connection string "
                "(postgresql://...) in backend/.env."
            )
        # SQLAlchemy no longer understands the legacy postgres:// scheme.
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if not url.startswith(("sqlite://", "postgresql://", "postgresql+psycopg://")):
            raise ValueError(
                "DATABASE_URL must use postgresql:// or postgresql+psycopg:// "
                "(sqlite:///:memory: is allowed for tests only)"
            )
        # Policy: users must never be persisted to a local SQLite file. Only an
        # in-memory database is permitted, and only because the test suite needs
        # it (it is discarded when the process exits, so nothing is stored).
        if url.startswith("sqlite"):
            memory_urls = {"sqlite://", "sqlite:///:memory:"}
            if url not in memory_urls and not url.startswith("sqlite:///file::memory:"):
                raise ValueError(
                    "Local file-based SQLite is disabled: users must be stored only in "
                    "the remote (Neon) database. Set DATABASE_URL to your postgresql:// "
                    "connection string. In-memory SQLite (sqlite:///:memory:) remains "
                    "available to automated tests."
                )
        return url

    # JWT Authentication
    # An empty value is allowed only outside production, where an ephemeral
    # development-only secret is generated at startup.
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    JWT_ISSUER: str = "clubsphere-api"
    JWT_AUDIENCE: str = "clubsphere-web"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=90)
    # Short window in which a just-rotated token can be retried by another tab
    # without revoking the whole session family.
    REFRESH_ROTATION_GRACE_SECONDS: int = Field(default=30, ge=1, le=300)

    # Refresh cookie
    REFRESH_COOKIE_NAME: str = "clubsphere_refresh"
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    COOKIE_SECURE: Optional[bool] = None
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "strict"
    COOKIE_DOMAIN: Optional[str] = None

    # Passwords / Argon2id
    PASSWORD_MIN_LENGTH: int = Field(default=8, ge=8, le=128)
    PASSWORD_MAX_LENGTH: int = Field(default=128, ge=8, le=1024)
    ARGON2_TIME_COST: int = Field(default=3, ge=1, le=10)
    ARGON2_MEMORY_COST: int = Field(default=65536, ge=8192)
    ARGON2_PARALLELISM: int = Field(default=4, ge=1, le=16)

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        if isinstance(v, (list, str)):
            return v  # type: ignore[return-value]
        raise ValueError(v)

    # Host / proxy / HTTPS
    ALLOWED_HOSTS: Union[str, List[str]] = ["*"]
    TRUSTED_PROXY_IPS: Union[str, List[str]] = ["*", "127.0.0.1", "::1"]

    @field_validator("ALLOWED_HOSTS", "TRUSTED_PROXY_IPS", mode="before")
    @classmethod
    def assemble_string_lists(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v  # type: ignore[return-value]

    # None means "enabled in production/staging only".
    FORCE_HTTPS: Optional[bool] = None
    HSTS_SECONDS: int = Field(default=31536000, ge=0)
    HSTS_INCLUDE_SUBDOMAINS: bool = True
    HSTS_PRELOAD: bool = False

    MAX_REQUEST_BODY_BYTES: int = Field(default=2 * 1024 * 1024, ge=1024)

    # Azure Blob Storage & File Uploads
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER_NAME: str = "clubsphere-uploads"
    AZURE_STORAGE_USE_EMULATOR: bool = True
    LOCAL_UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_MIME_TYPES: Union[str, List[str]] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    @field_validator("ALLOWED_MIME_TYPES", mode="before")
    @classmethod
    def assemble_mime_types(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v  # type: ignore[return-value]

    # Security & Rate Limiting
    RATE_LIMIT_LOGIN_ATTEMPTS: int = Field(default=15, ge=1, le=100)
    RATE_LIMIT_REGISTER_ATTEMPTS: int = Field(default=15, ge=1, le=100)
    RATE_LIMIT_REFRESH_ATTEMPTS: int = Field(default=60, ge=1, le=1000)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=10, le=86400)
    RATE_LIMIT_BLOCK_SECONDS: int = Field(default=60, ge=10, le=86400)

    @property
    def secure_cookies(self) -> bool:
        if self.COOKIE_SECURE is not None:
            return self.COOKIE_SECURE
        return self.ENVIRONMENT in ("production", "staging")

    @property
    def force_https(self) -> bool:
        if self.FORCE_HTTPS is not None:
            return self.FORCE_HTTPS
        return self.ENVIRONMENT in ("production", "staging")

    @property
    def docs_enabled(self) -> bool:
        if self.DOCS_ENABLED is not None:
            return self.DOCS_ENABLED
        return self.ENVIRONMENT != "production"

    @model_validator(mode="after")
    def validate_production_hardening(self):
        secret = (self.JWT_SECRET_KEY or "").strip()
        is_weak = (
            not secret
            or secret.lower() in {s.lower() for s in PLACEHOLDER_SECRETS}
            or len(secret) < 32
        )
        if is_weak:
            if self.ENVIRONMENT in ("production", "staging"):
                raise ValueError(
                    "JWT_SECRET_KEY is missing, a placeholder, or too short. "
                    "Generate one with: openssl rand -hex 32"
                )
            # Ephemeral development/test secret. Tokens do not survive a restart,
            # which is acceptable outside production and avoids a hardcoded secret.
            self.JWT_SECRET_KEY = secrets.token_urlsafe(48)

        if self.ENVIRONMENT in ("production", "staging"):
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production/staging")
            if self.AUTO_CREATE_SCHEMA:
                raise ValueError(
                    "AUTO_CREATE_SCHEMA must be false in production/staging; run alembic upgrade head"
                )
            if "*" in self.CORS_ORIGINS:
                raise ValueError("Wildcard CORS origins are not allowed in production/staging")
            if "*" in self.ALLOWED_HOSTS:
                raise ValueError("ALLOWED_HOSTS must be explicit in production/staging")
            if self.COOKIE_SAMESITE == "none" and not self.secure_cookies:
                raise ValueError("SameSite=None cookies require Secure cookies")
            if self.COOKIE_SAMESITE == "none" and not self.CORS_ORIGINS:
                raise ValueError("SameSite=None requires explicit CORS origins")

        if self.COOKIE_SAMESITE == "none" and not self.secure_cookies:
            raise ValueError("SameSite=None cookies require Secure cookies")

        if self.PASSWORD_MAX_LENGTH < self.PASSWORD_MIN_LENGTH:
            raise ValueError("PASSWORD_MAX_LENGTH must be >= PASSWORD_MIN_LENGTH")

        return self


settings = Settings()
