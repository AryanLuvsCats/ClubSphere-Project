import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_v1_router
from app.core.academic_seed import seed_academic_data
from app.core.config import settings
from app.core.database import Base, check_db_health, close_db_connections, engine, get_db
from app.core.middleware import (
    BodySizeLimitMiddleware,
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.logging_filter import setup_secure_logging
from app.models.models import Role, RoleNameEnum

logger = logging.getLogger("clubsphere")
setup_secure_logging()


def seed_baseline_data():
    """Ensure baseline roles and academic data (branches + programs) exist for local development and testing."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        # Seed Roles
        for role_name in [
            RoleNameEnum.STUDENT.value,
            RoleNameEnum.CLUB_MANAGER.value,
            RoleNameEnum.FACULTY.value,
            RoleNameEnum.HOD.value,
            RoleNameEnum.ADMINISTRATOR.value,
        ]:
            existing_role = db.query(Role).filter(Role.RoleName == role_name).first()
            if not existing_role:
                db.add(Role(RoleName=role_name))

        db.commit()

        # Seed academic data (branches + programs) from JSON if empty
        summary = seed_academic_data(db)
        if summary.get("seeded"):
            logger.info(
                "Academic seed: %s branches, %s programs loaded.",
                summary["branches"],
                summary["programs"],
            )

        # Clean up any expired rate limiting throttle records
        from app.core.rate_limit import cleanup_expired_throttle_rows
        cleanup_expired_throttle_rows(db)
    except Exception:
        db.rollback()
        # Never log the exception text here: SQLAlchemy errors can include a
        # database URL, and this runs during startup.
        logger.exception("Baseline seed warning")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tests run against an isolated in-memory SQLite database created by
    # tests/conftest.py, so they must never touch the configured database.
    if settings.ENVIRONMENT == "testing":
        yield
        return

    # Startup: ensure tables and baseline seed data exist.
    # AUTO_CREATE_SCHEMA only creates missing tables; it never alters existing
    # ones. Use Alembic migrations for schema changes.
    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)
    seed_baseline_data()
    yield
    # Shutdown logic: cleanly dispose the database connection pool
    close_db_connections()


def create_application() -> FastAPI:
    docs_enabled = settings.docs_enabled
    app = FastAPI(
        title="ClubSphere API",
        version="1.0.0",
        description="University Club & Activity Lifecycle Management System — Backend REST APIs",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    origins_list = (
        [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
        if isinstance(settings.CORS_ORIGINS, str)
        else settings.CORS_ORIGINS
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-Requested-With",
        ],
        max_age=600,
    )

    if settings.ALLOWED_HOSTS and "*" not in settings.ALLOWED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )

    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(HTTPSRedirectMiddleware)

    if settings.ENVIRONMENT != "testing":
        @app.exception_handler(Exception)
        async def unhandled_exception_handler(request: Request, exc: Exception):
            logger.exception("Unhandled request error on %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )

    # Liveness check for container orchestrators (Render / Kubernetes)
    @app.get("/health/live", tags=["Health"])
    def liveness_check():
        return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}

    # Root health smoke check
    @app.get("/health", tags=["Health"])
    def root_health_check(db: Session = Depends(get_db)):
        is_db_healthy = check_db_health(db)
        timestamp = datetime.now(timezone.utc).isoformat()
        if not is_db_healthy:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "degraded",
                    "app": settings.APP_NAME,
                    "database": "disconnected",
                    "timestamp": timestamp,
                },
            )
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
            "database": "connected",
            "timestamp": timestamp,
        }

    # Mount versioned API routes
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
