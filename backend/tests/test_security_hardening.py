import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_password_hash,
    token_digest,
)
from app.main import app
from app.models.models import (
    AuthThrottle,
    Branch,
    Club,
    ClubProposal,
    Event,
    EventRegistration,
    Program,
    RefreshSession,
    Role,
    RoleNameEnum,
    User,
)


def _make_user(db, email: str, role_name: str, program_id: int | None = None) -> User:
    role = db.query(Role).filter(Role.RoleName == role_name).first()
    user = User(
        Email=email,
        PasswordHash=get_password_hash("Password@123"),
        FullName=email.split("@")[0],
        RoleId=role.RoleId,
        ProgramId=program_id,
        IsActive=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _token(user: User) -> str:
    return create_access_token(
        subject=user.UserId,
        role=user.role.RoleName,
        token_version=user.TokenVersion,
    )


def _clear_throttle(db):
    db.query(AuthThrottle).delete()
    db.commit()


def test_security_headers_and_api_csp(client):
    response = client.get("/api/v1/clubs")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_hsts_emitted_for_trusted_https_proxy(client, monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", ["testclient"])
    response = client.get(
        "/api/v1/clubs",
        headers={"X-Forwarded-Proto": "https"},
    )
    assert response.status_code == 200
    assert "max-age=" in response.headers["strict-transport-security"]


def test_https_redirect_when_forced(client, monkeypatch):
    monkeypatch.setattr(settings, "FORCE_HTTPS", True)
    response = client.get("/api/v1/clubs", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].startswith("https://")


def test_login_response_never_exposes_password_hash_or_refresh_token(client, student_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": student_user.Email, "password": "Password@123"},
    )
    assert response.status_code == 200
    body = response.text
    assert "PasswordHash" not in body
    assert "$argon2" not in body
    assert "refresh_token" not in body


def test_password_hash_is_argon2id(client, student_user, db_session):
    db_session.refresh(student_user)
    assert student_user.PasswordHash.startswith("$argon2id$")


def test_logout_revokes_access_and_refresh_sessions(client, db_session):
    logout_user = _make_user(
        db_session,
        f"logout-{uuid.uuid4().hex[:8]}@univ.edu",
        RoleNameEnum.STUDENT.value,
        db_session.query(Program).filter(Program.ProgramKey == "btech_cse").first().ProgramId,
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": logout_user.Email, "password": "Password@123"},
    )
    token = login.json()["access_token"]
    assert client.cookies.get("clubsphere_refresh")

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout.status_code == 200

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_login_throttle_blocks_repeated_failures(client, student_user, db_session, monkeypatch):
    _clear_throttle(db_session)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "RATE_LIMIT_BLOCK_SECONDS", 60)

    try:
        first = client.post(
            "/api/v1/auth/login",
            json={"email": student_user.Email, "password": "WrongPassword1"},
        )
        second = client.post(
            "/api/v1/auth/login",
            json={"email": student_user.Email, "password": "WrongPassword2"},
        )
        third = client.post(
            "/api/v1/auth/login",
            json={"email": student_user.Email, "password": "WrongPassword3"},
        )
        assert first.status_code == 401
        assert second.status_code == 401
        assert third.status_code == 429
        assert "Retry-After" in third.headers
    finally:
        _clear_throttle(db_session)


def test_refresh_reuse_outside_grace_revokes_family(
    client, student_user, db_session, monkeypatch
):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": student_user.Email, "password": "Password@123"},
    )
    old_refresh = client.cookies.get("clubsphere_refresh")
    assert old_refresh

    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200

    # Age the rotation beyond the grace window, then present the old cookie.
    old_session = (
        db_session.query(RefreshSession)
        .filter(RefreshSession.TokenHash == token_digest(old_refresh))
        .first()
    )
    assert old_session is not None
    old_session.ReplacedAt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        minutes=5
    )
    db_session.commit()

    client.cookies.set("clubsphere_refresh", old_refresh)
    reused = client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401

    # The entire family is revoked, including the token issued by the rotation.
    active = (
        db_session.query(RefreshSession)
        .filter(
            RefreshSession.FamilyId == old_session.FamilyId,
            RefreshSession.RevokedAt.is_(None),
        )
        .count()
    )
    assert active == 0


def test_extra_fields_are_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "someone@univ.edu",
            "password": "Password@123",
            "role": "Administrator",
        },
    )
    assert response.status_code == 422


def test_html_in_full_name_is_rejected(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"xss-{uuid.uuid4().hex[:8]}@univ.edu",
            "password": "SecurePassword123!",
            "full_name": "<script>alert(1)</script>",
        },
    )
    assert response.status_code == 422


def test_search_is_parameterized_and_does_not_bypass_status(
    client, manager_user, db_session
):
    pending = Club(
        Name=f"Hidden Pending {uuid.uuid4().hex[:8]}",
        ProgramId=manager_user.ProgramId,
        ManagerUserId=manager_user.UserId,
        Description="pending club",
        Status="pending",
    )
    db_session.add(pending)
    db_session.commit()

    response = client.get(
        "/api/v1/clubs",
        params={"search": "%' OR 1=1 --"},
    )
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert pending.Name not in names


def test_pending_club_hidden_from_public_but_visible_to_manager(
    client, manager_user, manager_token, db_session
):
    hidden = Club(
        Name=f"Pending Visibility {uuid.uuid4().hex[:8]}",
        ProgramId=manager_user.ProgramId,
        ManagerUserId=manager_user.UserId,
        Description="pending club",
        Status="pending",
    )
    db_session.add(hidden)
    db_session.commit()
    db_session.refresh(hidden)

    assert client.get(f"/api/v1/clubs/{hidden.ClubId}").status_code == 404
    assert client.get("/api/v1/clubs", params={"status": "pending"}).status_code == 403

    visible = client.get(
        f"/api/v1/clubs/{hidden.ClubId}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert visible.status_code == 200
    assert visible.json()["status"] == "pending"


def test_draft_event_hidden_from_public_but_visible_to_manager(
    client, manager_user, manager_token, db_session
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    draft = Event(
        ClubId=db_session.query(Club).first().ClubId if db_session.query(Club).first() else 1,
        Title=f"Draft Event {uuid.uuid4().hex[:8]}",
        VenueText="Secret venue",
        EventDate=now + timedelta(days=3),
        RegistrationDeadline=now + timedelta(days=2),
        Capacity=10,
        Status="draft",
        CreatedByUserId=manager_user.UserId,
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)

    assert client.get(f"/api/v1/events/{draft.EventId}").status_code == 404
    assert client.get("/api/v1/events", params={"status": "draft"}).status_code == 403

    visible = client.get(
        f"/api/v1/events/{draft.EventId}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert visible.status_code == 200
    assert visible.json()["status"] == "draft"


def test_cross_branch_faculty_cannot_view_or_review_proposal(
    client, student_user, db_session
):
    branch = Branch(
        BranchKey=f"other-{uuid.uuid4().hex[:8]}",
        Name=f"Other Branch {uuid.uuid4().hex[:8]}",
        DegreeLevel="postgraduate",
        SortOrder=99,
    )
    db_session.add(branch)
    db_session.flush()
    program = Program(
        ProgramKey=f"other-{uuid.uuid4().hex[:8]}",
        BranchId=branch.BranchId,
        Name="Other Program",
        FullName="Other Program",
        SortOrder=99,
    )
    db_session.add(program)
    db_session.commit()

    other_faculty = _make_user(
        db_session,
        f"other-faculty-{uuid.uuid4().hex[:8]}@univ.edu",
        RoleNameEnum.FACULTY.value,
        program.ProgramId,
    )
    proposal = ClubProposal(
        ApplicantUserId=student_user.UserId,
        ProposedName=f"Cross Branch Proposal {uuid.uuid4().hex[:8]}",
        ProgramId=student_user.ProgramId,
        Description="A valid proposal description for branch scope testing.",
        Status="submitted",
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)

    headers = {"Authorization": f"Bearer {_token(other_faculty)}"}
    assert client.get(f"/api/v1/proposals/{proposal.ProposalId}", headers=headers).status_code == 404
    review = client.post(
        f"/api/v1/proposals/{proposal.ProposalId}/review",
        json={"decision": "approve"},
        headers=headers,
    )
    assert review.status_code == 403


def test_hod_analytics_are_branch_scoped(client, db_session):
    btech = db_session.query(Branch).filter(Branch.BranchKey == "btech").first()
    other_branch = Branch(
        BranchKey=f"analytics-{uuid.uuid4().hex[:8]}",
        Name=f"Analytics Branch {uuid.uuid4().hex[:8]}",
        DegreeLevel="postgraduate",
        SortOrder=100,
    )
    db_session.add(other_branch)
    db_session.flush()
    other_program = Program(
        ProgramKey=f"analytics-{uuid.uuid4().hex[:8]}",
        BranchId=other_branch.BranchId,
        Name="Analytics Program",
        FullName="Analytics Program",
        SortOrder=100,
    )
    db_session.add(other_program)
    db_session.commit()

    manager = _make_user(
        db_session,
        f"analytics-manager-{uuid.uuid4().hex[:8]}@univ.edu",
        RoleNameEnum.CLUB_MANAGER.value,
        btech_branch_program_id := db_session.query(Program)
        .filter(Program.BranchId == btech.BranchId)
        .first()
        .ProgramId,
    )
    other_club = Club(
        Name=f"Other Branch Club {uuid.uuid4().hex[:8]}",
        ProgramId=other_program.ProgramId,
        ManagerUserId=manager.UserId,
        Description="must not appear in HOD analytics",
        Status="active",
    )
    db_session.add(other_club)
    db_session.commit()

    hod = _make_user(
        db_session,
        f"analytics-hod-{uuid.uuid4().hex[:8]}@univ.edu",
        RoleNameEnum.HOD.value,
        btech_branch_program_id,
    )
    response = client.get(
        "/api/v1/admin/analytics/overview",
        headers={"Authorization": f"Bearer {_token(hod)}"},
    )
    assert response.status_code == 200
    data = response.json()
    branch_ids = [item["branch_id"] for item in data["branch_metrics"]]
    assert branch_ids == [btech.BranchId]


def test_unregistered_student_cannot_read_outcome(client, student2_token, db_session):
    club = db_session.query(Club).first()
    manager = db_session.query(User).first()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    event = Event(
        ClubId=club.ClubId,
        Title=f"Outcome Privacy {uuid.uuid4().hex[:8]}",
        VenueText="Room 1",
        EventDate=now + timedelta(days=1),
        RegistrationDeadline=now + timedelta(days=1),
        Capacity=10,
        Status="completed",
        CreatedByUserId=manager.UserId,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    from app.models.models import EventOutcome

    db_session.add(
        EventOutcome(
            EventId=event.EventId,
            Summary="Private outcome",
            AttendanceCountSnapshot=0,
            SubmittedByUserId=manager.UserId,
        )
    )
    db_session.commit()

    response = client.get(
        f"/api/v1/events/{event.EventId}/outcomes",
        headers={"Authorization": f"Bearer {student2_token}"},
    )
    assert response.status_code == 404


def test_upload_rejects_spoofed_magic_bytes(client, student_token, student_user, db_session):
    proposal = ClubProposal(
        ApplicantUserId=student_user.UserId,
        ProposedName=f"Spoof Upload {uuid.uuid4().hex[:8]}",
        ProgramId=student_user.ProgramId,
        Description="A proposal for upload validation.",
        Status="submitted",
    )
    db_session.add(proposal)
    db_session.commit()

    response = client.post(
        "/api/v1/uploads",
        headers={"Authorization": f"Bearer {student_token}"},
        files={"file": ("fake.pdf", io.BytesIO(b"not a pdf"), "application/pdf")},
        data={"entity_type": "ClubProposals", "entity_id": proposal.ProposalId},
    )
    assert response.status_code == 400


def test_cors_rejects_untrusted_origin(client):
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_rate_limit_recovery_after_block_expires(client, student_user, db_session, monkeypatch):
    _clear_throttle(db_session)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 300)
    monkeypatch.setattr(settings, "RATE_LIMIT_BLOCK_SECONDS", 1)

    try:
        # Trigger block (attempts 1 and 2 fail, attempt 3 is throttled)
        client.post("/api/v1/auth/login", json={"email": student_user.Email, "password": "WrongPassword1"})
        client.post("/api/v1/auth/login", json={"email": student_user.Email, "password": "WrongPassword2"})
        third = client.post("/api/v1/auth/login", json={"email": student_user.Email, "password": "WrongPassword3"})
        assert third.status_code == 429

        # Age the block so it has expired
        from app.models.models import AuthThrottle
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.query(AuthThrottle).update(
            {AuthThrottle.BlockedUntil: now - timedelta(seconds=1)},
            synchronize_session=False,
        )
        db_session.commit()

        # Legitimate user attempts login with correct password -> must succeed
        recovery = client.post(
            "/api/v1/auth/login",
            json={"email": student_user.Email, "password": "Password@123"},
        )
        assert recovery.status_code == 200
        assert "access_token" in recovery.json()
    finally:
        _clear_throttle(db_session)


def test_csrf_cross_site_request_forbidden(client, student_user):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": student_user.Email, "password": "Password@123"},
    )
    assert login.status_code == 200

    # Cross-site refresh attempt via Sec-Fetch-Site must be blocked
    cross_site = client.post(
        "/api/v1/auth/refresh",
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert cross_site.status_code == 403
    assert "Cross-site requests" in cross_site.json()["detail"]


def test_admin_users_list_restricted_to_administrator(client, student_token, manager_token, admin_token):
    # Student forbidden
    assert client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {student_token}"}).status_code == 403
    # Manager forbidden
    assert client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {manager_token}"}).status_code == 403
    # Administrator permitted
    res = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] > 0


def test_admin_self_role_modification_rejected(client, admin_user, admin_token):
    # Administrator cannot modify their own role
    res = client.put(
        f"/api/v1/admin/users/{admin_user.UserId}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role_name": "Student"},
    )
    assert res.status_code == 400
    assert "cannot modify their own role" in res.json()["detail"]


def test_admin_update_user_role_invalidates_sessions(client, admin_token, db_session):
    fresh_user = _make_user(
        db_session,
        f"role-change-{uuid.uuid4().hex[:8]}@univ.edu",
        RoleNameEnum.STUDENT.value,
    )
    fresh_token = _token(fresh_user)

    # User starts with active access token
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh_token}"})
    assert me.status_code == 200

    # Admin promotes Student to Club Manager
    promote = client.put(
        f"/api/v1/admin/users/{fresh_user.UserId}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role_name": RoleNameEnum.CLUB_MANAGER.value},
    )
    assert promote.status_code == 200
    assert promote.json()["role"] == RoleNameEnum.CLUB_MANAGER.value

    # Old access token is now invalid due to TokenVersion increment
    me_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh_token}"})
    assert me_after.status_code == 401


def test_sensitive_data_logging_filter():
    from app.core.logging_filter import mask_sensitive_text
    sample = (
        "User login failed with password='MySecretPassword123' and token Bearer eyJhbGciOiJIUzI1Ni. "
        "Connecting to postgresql://user:super_secret_pw@db.neon.tech/neondb, cookie clubsphere_refresh=secret_cookie_token;"
    )
    masked = mask_sensitive_text(sample)
    assert "MySecretPassword123" not in masked
    assert "eyJhbGciOiJIUzI1Ni" not in masked
    assert "super_secret_pw" not in masked
    assert "secret_cookie_token" not in masked
    assert "[REDACTED]" in masked


def test_production_debug_mode_enforced():
    from pydantic import ValidationError
    from app.core.config import Settings
    import pytest

    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            DATABASE_URL="sqlite:///./test.db",
            JWT_SECRET_KEY="a" * 32,
            AUTO_CREATE_SCHEMA=False,
            CORS_ORIGINS=["http://localhost:5173"],
            ALLOWED_HOSTS=["localhost"],
        )
