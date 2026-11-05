import uuid
from datetime import timedelta
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import (
    clear_login_failures,
    client_ip,
    enforce_login_limit,
    enforce_refresh_limit,
    enforce_register_limit,
    record_login_failure,
    record_refresh_failure,
    record_register_attempt,
    utc_now_naive,
)
from app.core.rbac import get_current_active_user, normalize_role
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    password_needs_rehash,
    token_digest,
    validate_password_length,
    verify_dummy_password,
    verify_password,
)
from app.models.models import (
    Program,
    RefreshSession,
    Role,
    RoleNameEnum,
    User,
)
from app.schemas.auth import (
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        user_id=user.UserId,
        email=user.Email,
        full_name=user.FullName,
        role=user.role.RoleName if user.role else RoleNameEnum.STUDENT.value,
        program_id=user.ProgramId,
        program_name=user.program.FullName if user.program else None,
        branch_id=user.program.BranchId if user.program else None,
        branch_name=user.program.branch.Name if user.program else None,
        is_active=user.IsActive,
        created_at=user.CreatedAt,
    )


def _token_response(user: User) -> TokenResponse:
    role_name = user.role.RoleName if user.role else RoleNameEnum.STUDENT.value
    access_token = create_access_token(
        subject=user.UserId,
        role=role_name,
        token_version=user.TokenVersion,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=role_name,
        user_id=user.UserId,
        full_name=user.FullName,
        email=user.Email,
    )


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.secure_cookies,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.secure_cookies,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )


def _assert_allowed_origin(request: Request) -> None:
    """Reject cross-site browser requests to cookie-authenticated endpoints.

    Combines Sec-Fetch-Site validation, Origin allowlist matching, and
    Referer verification to defend against Cross-Site Request Forgery (CSRF).
    """
    sec_fetch_site = request.headers.get("sec-fetch-site")
    if sec_fetch_site and sec_fetch_site.lower() == "cross-site":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-site requests to this endpoint are strictly forbidden",
        )

    origin = request.headers.get("origin")
    if origin:
        if origin not in settings.CORS_ORIGINS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request origin is not allowed",
            )
        return

    # If Origin is omitted by browser/client, check Referer
    referer = request.headers.get("referer")
    if referer:
        # Check that referer starts with one of the allowed origins
        allowed = any(referer.startswith(f"{allowed_origin}/") or referer == allowed_origin for allowed_origin in settings.CORS_ORIGINS)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request referer is not allowed",
            )


def _new_refresh_session(
    db: Session,
    user: User,
    request: Request,
    family_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Tuple[str, RefreshSession]:
    raw_token, digest = generate_refresh_token()
    now = utc_now_naive()
    session = RefreshSession(
        SessionId=session_id or uuid.uuid4().hex,
        UserId=user.UserId,
        FamilyId=family_id or uuid.uuid4().hex,
        TokenHash=digest,
        IssuedAt=now,
        ExpiresAt=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        IpAddress=client_ip(request)[:45],
        UserAgent=(request.headers.get("user-agent") or "")[:255],
    )
    db.add(session)
    return raw_token, session


def _revoke_family(db: Session, family_id: str) -> None:
    now = utc_now_naive()
    db.query(RefreshSession).filter(
        RefreshSession.FamilyId == family_id,
        RefreshSession.RevokedAt.is_(None),
    ).update({RefreshSession.RevokedAt: now}, synchronize_session=False)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new student. Elevated roles remain administrator-managed."""
    enforce_register_limit(db, request)
    record_register_attempt(db, request)

    password = payload.password.get_secret_value()
    validate_password_length(password)

    email = payload.email.lower()
    existing_user = db.query(User).filter(User.Email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address is already registered",
        )

    student_role = db.query(Role).filter(Role.RoleName == RoleNameEnum.STUDENT.value).first()
    if not student_role:
        student_role = Role(RoleName=RoleNameEnum.STUDENT.value)
        db.add(student_role)
        db.flush()

    if payload.program_id:
        program = db.query(Program).filter(Program.ProgramId == payload.program_id).first()
        if not program:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected program does not exist",
            )

    new_user = User(
        Email=email,
        PasswordHash=get_password_hash(password),
        FullName=payload.full_name,
        RoleId=student_role.RoleId,
        ProgramId=payload.program_id,
        IsActive=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return _user_response(new_user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate and set an HttpOnly refresh cookie.

    The access token is returned in the JSON body and should be kept in memory.
    """
    email = payload.email.lower()
    password = payload.password.get_secret_value()
    enforce_login_limit(db, request, email)

    user = db.query(User).filter(User.Email == email).first()
    if not user:
        verify_dummy_password(password)
        record_login_failure(db, request, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user.PasswordHash):
        record_login_failure(db, request, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Do not reveal whether the account exists but is disabled.
    if not user.IsActive:
        record_login_failure(db, request, email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clear_login_failures(db, request, email)

    # Transparently upgrade legacy bcrypt hashes to Argon2id on successful login.
    if password_needs_rehash(user.PasswordHash):
        user.PasswordHash = get_password_hash(password)

    raw_refresh, _ = _new_refresh_session(db, user, request)
    db.commit()
    db.refresh(user)

    _set_refresh_cookie(response, raw_refresh)
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Rotate the refresh cookie and return a new short-lived access token."""
    _assert_allowed_origin(request)
    enforce_refresh_limit(db, request)

    raw_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw_token:
        record_refresh_failure(db, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session is missing. Please log in again.",
        )

    now = utc_now_naive()
    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.TokenHash == token_digest(raw_token))
        .first()
    )
    if not session:
        record_refresh_failure(db, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session is invalid. Please log in again.",
        )

    if session.ExpiresAt <= now:
        session.RevokedAt = now
        db.commit()
        record_refresh_failure(db, request)
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session has expired. Please log in again.",
        )

    if session.RevokedAt is not None or session.ReplacedBySessionId:
        # A second tab may race the first rotation. Allow a brief retry window
        # without revoking the family; the browser cookie has already been
        # replaced by the winning request.
        if (
            session.ReplacedAt is not None
            and (now - session.ReplacedAt).total_seconds()
            <= settings.REFRESH_ROTATION_GRACE_SECONDS
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refresh already rotated. Retry with the updated cookie.",
                headers={"Retry-After": "1"},
            )

        # Reuse of an already-rotated or revoked token is treated as theft.
        _revoke_family(db, session.FamilyId)
        db.commit()
        record_refresh_failure(db, request)
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session is no longer valid. Please log in again.",
        )

    user = db.query(User).filter(User.UserId == session.UserId).first()
    if not user or not user.IsActive:
        _revoke_family(db, session.FamilyId)
        db.commit()
        record_refresh_failure(db, request)
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session is no longer valid. Please log in again.",
        )

    new_session_id = uuid.uuid4().hex
    session.RevokedAt = now
    session.ReplacedAt = now
    session.ReplacedBySessionId = new_session_id
    raw_refresh, _ = _new_refresh_session(
        db,
        user,
        request,
        family_id=session.FamilyId,
        session_id=new_session_id,
    )
    db.commit()
    db.refresh(user)

    _set_refresh_cookie(response, raw_refresh)
    return _token_response(user)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Revoke every refresh session and invalidate outstanding access tokens."""
    _assert_allowed_origin(request)
    now = utc_now_naive()
    db.query(RefreshSession).filter(
        RefreshSession.UserId == current_user.UserId,
        RefreshSession.RevokedAt.is_(None),
    ).update({RefreshSession.RevokedAt: now}, synchronize_session=False)
    current_user.TokenVersion += 1
    db.commit()
    _clear_refresh_cookie(response)
    return {"message": "Successfully logged out. All active sessions have been revoked."}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    response: Response,
    current_user: User = Depends(get_current_active_user),
):
    """Return the authenticated user's profile."""
    response.headers["Cache-Control"] = "no-store"
    return _user_response(current_user)
