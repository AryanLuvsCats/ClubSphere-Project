import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Union

import bcrypt
import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

# Argon2id is the only algorithm used for new hashes. Parameters are
# configurable so deployments can tune memory cost without a code change.
_password_hasher = PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_COST,
    parallelism=settings.ARGON2_PARALLELISM,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

# Used to keep failed-login timing consistent for unknown accounts.
DUMMY_PASSWORD_HASH = _password_hasher.hash("clubsphere-dummy-password-not-a-real-account")


def validate_password_length(password: str) -> None:
    """Reject passwords outside the configured bounds before hashing."""
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long",
        )
    if len(password) > settings.PASSWORD_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at most {settings.PASSWORD_MAX_LENGTH} characters long",
        )


def get_password_hash(password: str) -> str:
    """Hash a plaintext password with Argon2id."""
    validate_password_length(password)
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against an Argon2id or legacy bcrypt hash.

    Existing bcrypt hashes are accepted so users are not locked out; callers
    should rehash after a successful login via :func:`password_needs_rehash`.
    """
    if not hashed_password:
        return False

    try:
        if hashed_password.startswith("$2"):
            # Legacy bcrypt hash. bcrypt only considers the first 72 bytes.
            return bcrypt.checkpw(
                plain_password.encode("utf-8")[:72],
                hashed_password.encode("utf-8"),
            )
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, ValueError, TypeError):
        return False
    except Exception:
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    """Return True when the stored hash should be upgraded to current Argon2id params."""
    if not hashed_password or hashed_password.startswith("$2"):
        return True
    try:
        return _password_hasher.check_needs_rehash(hashed_password)
    except (InvalidHashError, ValueError, TypeError):
        return True


def verify_dummy_password(password: str) -> None:
    """Perform a hash verification to reduce user-enumeration timing signals."""
    try:
        _password_hasher.verify(DUMMY_PASSWORD_HASH, password)
    except Exception:
        pass


def _base_payload(subject: Union[str, int], role: str, token_version: int) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "sub": str(subject),
        "role": role,
        "token_version": token_version,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }


def create_access_token(
    subject: Union[str, int],
    role: str,
    token_version: int = 1,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a short-lived signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = _base_payload(subject, role, token_version)
    payload.update({"type": "access", "exp": int(expire.timestamp())})
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def generate_refresh_token() -> Tuple[str, str]:
    """Create an opaque refresh token and its SHA-256 digest for storage."""
    raw = secrets.token_urlsafe(48)
    return raw, token_digest(raw)


def token_digest(raw_token: str) -> str:
    """Hash an opaque token before persisting or comparing it."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def decode_token(token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """Decode a JWT and validate signature, issuer, audience, and expiry."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature or payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if expected_type is not None and payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token type. {expected_type.capitalize()} token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def extract_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
