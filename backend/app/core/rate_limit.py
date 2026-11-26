"""Database-backed brute-force protection for authentication endpoints.

The limiter intentionally has no in-process state: it survives restarts and
works across multiple Uvicorn/Gunicorn workers. Identifiers are hashed before
storage so raw email addresses and IPs are not kept in the throttle table.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import parse_rate_limit, settings
from app.models.models import AuthThrottle


def utc_now_naive() -> datetime:
    """Return naive UTC, matching the DateTime columns used by SQLite/Postgres."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_key(scope: str, identifier: str) -> str:
    return hashlib.sha256(f"{scope}:{identifier}".encode("utf-8")).hexdigest()


def client_ip(request: Request) -> str:
    """Extract the real client IP behind reverse proxies (e.g., Render / Cloudflare).

    Reads the first IP in X-Forwarded-For or CF-Connecting-IP (falling back to
    X-Real-IP, then request.client.host only when no proxy header is present).
    """
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for

    cf_ip = request.headers.get("cf-connecting-ip", "").strip()
    if cf_ip:
        return cf_ip

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip

    return request.client.host if request.client else "unknown"


def _auth_limit_config(configured_attempts: int) -> tuple[int, int]:
    """Resolve effective (attempts, window_seconds) from AUTH_RATE_LIMIT and test overrides."""
    auth_attempts, auth_window = parse_rate_limit(settings.AUTH_RATE_LIMIT)
    if configured_attempts < min(20, auth_attempts):
        attempts = configured_attempts
    else:
        attempts = auth_attempts
    window = (
        settings.RATE_LIMIT_WINDOW_SECONDS
        if auth_window == 60 and settings.RATE_LIMIT_WINDOW_SECONDS != 60
        else auth_window
    )
    return attempts, window


def _get_or_create(
    db: Session,
    scope: str,
    key_hash: str,
    now: datetime,
) -> AuthThrottle:
    row = (
        db.query(AuthThrottle)
        .filter(AuthThrottle.Scope == scope, AuthThrottle.KeyHash == key_hash)
        .first()
    )
    if row is None:
        row = AuthThrottle(
            Scope=scope,
            KeyHash=key_hash,
            FailureCount=0,
            WindowStartedAt=now,
            BlockedUntil=None,
            UpdatedAt=now,
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            # Another worker inserted the same (scope, key) at the same time.
            db.rollback()
            row = (
                db.query(AuthThrottle)
                .filter(
                    AuthThrottle.Scope == scope,
                    AuthThrottle.KeyHash == key_hash,
                )
                .first()
            )
            if row is None:
                row = AuthThrottle(
                    Scope=scope,
                    KeyHash=key_hash,
                    FailureCount=0,
                    WindowStartedAt=now,
                    BlockedUntil=None,
                    UpdatedAt=now,
                )
                db.add(row)
    return row


def check_rate_limit(
    db: Session,
    scope: str,
    identifier: str,
    max_attempts: int,
    window_seconds: int,
    block_seconds: int,
) -> None:
    """Raise 429 when the identifier is currently blocked or over its limit."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    now = utc_now_naive()
    key_hash = _hash_key(scope, identifier)
    row = (
        db.query(AuthThrottle)
        .filter(AuthThrottle.Scope == scope, AuthThrottle.KeyHash == key_hash)
        .first()
    )
    if row is None:
        return

    if row.BlockedUntil and row.BlockedUntil > now:
        retry_after = max(1, int((row.BlockedUntil - now).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    # Legitimate user recovery: if a previous temporary block has expired,
    # reset failure count and clear the block so the user can authenticate.
    if row.BlockedUntil and row.BlockedUntil <= now:
        row.FailureCount = 0
        row.BlockedUntil = None
        row.WindowStartedAt = now
        row.UpdatedAt = now
        db.commit()
        return

    window_started = row.WindowStartedAt
    if window_started and window_started + timedelta(seconds=window_seconds) <= now:
        row.FailureCount = 0
        row.WindowStartedAt = now
        row.BlockedUntil = None
        row.UpdatedAt = now
        db.commit()
        return

    if row.FailureCount >= max_attempts:
        row.BlockedUntil = now + timedelta(seconds=block_seconds)
        row.UpdatedAt = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Please try again in {block_seconds} seconds.",
            headers={"Retry-After": str(block_seconds)},
        )


def record_failure(
    db: Session,
    scope: str,
    identifier: str,
    max_attempts: int,
    window_seconds: int,
    block_seconds: int,
) -> None:
    """Increment an attempt counter and start a block when the limit is reached."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    now = utc_now_naive()
    key_hash = _hash_key(scope, identifier)
    row = _get_or_create(db, scope, key_hash, now)

    if row.WindowStartedAt and row.WindowStartedAt + timedelta(seconds=window_seconds) <= now:
        row.FailureCount = 0
        row.WindowStartedAt = now
        row.BlockedUntil = None

    row.FailureCount += 1
    row.UpdatedAt = now
    if row.FailureCount >= max_attempts:
        row.BlockedUntil = now + timedelta(seconds=block_seconds)
    db.commit()


def clear_failures(db: Session, scope: str, identifier: str) -> None:
    """Remove counters after a successful attempt."""
    key_hash = _hash_key(scope, identifier)
    db.query(AuthThrottle).filter(
        AuthThrottle.Scope == scope,
        AuthThrottle.KeyHash == key_hash,
    ).delete(synchronize_session=False)
    db.commit()


def cleanup_expired_throttle_rows(db: Session, older_than_days: int = 1) -> int:
    """Best-effort cleanup of old, expired counters and blocks."""
    now = utc_now_naive()
    cutoff = now - timedelta(days=older_than_days)
    deleted = (
        db.query(AuthThrottle)
        .filter(
            (AuthThrottle.UpdatedAt < cutoff)
            | ((AuthThrottle.BlockedUntil.is_not(None)) & (AuthThrottle.BlockedUntil <= now))
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)


def enforce_login_limit(db: Session, request: Request, email: str) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    ip = client_ip(request)
    attempts, window_seconds = _auth_limit_config(settings.RATE_LIMIT_LOGIN_ATTEMPTS)
    ip_max_attempts = max(attempts * 5, 25)
    check_rate_limit(
        db,
        "login_ip",
        ip,
        ip_max_attempts,
        window_seconds,
        settings.RATE_LIMIT_BLOCK_SECONDS,
    )
    check_rate_limit(
        db,
        "login_account",
        email.lower(),
        attempts,
        window_seconds,
        settings.RATE_LIMIT_BLOCK_SECONDS,
    )


def record_login_failure(db: Session, request: Request, email: str) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    ip = client_ip(request)
    attempts, window_seconds = _auth_limit_config(settings.RATE_LIMIT_LOGIN_ATTEMPTS)
    ip_max_attempts = max(attempts * 5, 25)
    record_failure(
        db,
        "login_ip",
        ip,
        ip_max_attempts,
        window_seconds,
        settings.RATE_LIMIT_BLOCK_SECONDS,
    )
    record_failure(
        db,
        "login_account",
        email.lower(),
        attempts,
        window_seconds,
        settings.RATE_LIMIT_BLOCK_SECONDS,
    )


def clear_login_failures(db: Session, request: Request, email: str) -> None:
    # Only the account counter is reset. The IP counter deliberately survives
    # successful logins so an attacker cannot reset it by signing into their own
    # account between password guesses. It expires with the normal time window.
    clear_failures(db, "login_account", email.lower())


def enforce_register_limit(db: Session, request: Request) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    attempts, window_seconds = _auth_limit_config(settings.RATE_LIMIT_REGISTER_ATTEMPTS)
    check_rate_limit(
        db,
        "register_ip",
        client_ip(request),
        attempts,
        window_seconds,
        settings.RATE_LIMIT_BLOCK_SECONDS,
    )


def record_register_attempt(db: Session, request: Request) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    attempts, window_seconds = _auth_limit_config(settings.RATE_LIMIT_REGISTER_ATTEMPTS)
    record_failure(
        db,
        "register_ip",
        client_ip(request),
        attempts,
        window_seconds,
        settings.RATE_LIMIT_BLOCK_SECONDS,
    )


def enforce_refresh_limit(db: Session, request: Request) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    check_rate_limit(
        db,
        "refresh_ip",
        client_ip(request),
        settings.RATE_LIMIT_REFRESH_ATTEMPTS,
        settings.RATE_LIMIT_WINDOW_SECONDS,
        settings.RATE_LIMIT_BLOCK_SECONDS,
    )


def record_refresh_failure(db: Session, request: Request) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    record_failure(
        db,
        "refresh_ip",
        client_ip(request),
        settings.RATE_LIMIT_REFRESH_ATTEMPTS,
        settings.RATE_LIMIT_WINDOW_SECONDS,
        settings.RATE_LIMIT_BLOCK_SECONDS,
    )
