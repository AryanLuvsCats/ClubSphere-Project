"""Tests for Azure SQL T-SQL compatibility, Power BI view/analytics endpoints, Blob Storage, and Neon migration."""

import io
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from sqlalchemy import create_engine, schema
from sqlalchemy.dialects import mssql

from app.core.config import settings
from app.core.logging_filter import mask_sensitive_text
from app.core.security import get_password_hash
from app.db.session import Base
from app.models.models import (
    Branch,
    Club,
    ClubMembership,
    Event,
    EventRegistration,
    Program,
    Role,
    RoleNameEnum,
    User,
)
from app.services.analytics import ensure_analytics_views
from app.services.storage import blob_key_for_entity, read_stored_bytes, store_blob_or_local
from scripts.migrate_neon_to_azure_sql import migrate_databases, table_has_identity_pk


def test_tsql_ddl_has_no_postgresql_only_types():
    """Verify every ORM model compiles cleanly to T-SQL without TEXT/UUID/JSONB/SERIAL."""
    dialect = mssql.dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(schema.CreateTable(table).compile(dialect=dialect))
        assert "SERIAL" not in ddl
        assert "JSONB" not in ddl
        assert "UUID" not in ddl
        assert " TEXT " not in ddl  # Deprecated SQL Server TEXT breaks LOWER()/ilike
        if table.name not in {"UploadedFiles", "RefreshSessions"}:
            assert "IDENTITY(1,1)" in ddl


def test_logging_filter_masks_azure_sql_and_blob_secrets():
    sample = (
        "Connecting mssql+pyodbc://csadmin:TopSecret%4099@srv.database.windows.net:1433/clubsphere "
        "and PWD=AnotherSecret!; AccountKey=FakeKey123456==;EndpointSuffix=core.windows.net"
    )
    masked = mask_sensitive_text(sample)
    assert "TopSecret%4099" not in masked
    assert "AnotherSecret!" not in masked
    assert "FakeKey123456==" not in masked
    assert "[REDACTED]" in masked


def test_analytics_overview_and_club_view_endpoints(client, admin_token, hod_token, sample_club, sample_event, db_session):
    ensure_analytics_views(db_session.get_bind())
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.get("/api/v1/analytics/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["active_clubs"] >= 1
    assert any(c["club_id"] == sample_club.ClubId for c in data["club_summaries"])

    clubs_res = client.get("/api/v1/analytics/clubs", headers=headers)
    assert clubs_res.status_code == 200
    rows = clubs_res.json()
    matched = next(r for r in rows if r["club_id"] == sample_club.ClubId)
    assert matched["active_members"] >= 1
    assert matched["leadership_count"] >= 1
    assert matched["total_events"] >= 1

    # HOD analytics must stay branch-scoped
    hod_res = client.get("/api/v1/analytics/overview", headers={"Authorization": f"Bearer {hod_token}"})
    assert hod_res.status_code == 200
    hod_branches = {item["branch_id"] for item in hod_res.json()["branch_metrics"]}
    assert len(hod_branches) == 1


def test_analytics_json_export_to_storage(client, admin_token, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "AZURE_STORAGE_CONNECTION_STRING", "")
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.post("/api/v1/analytics/export", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["blob_path"].startswith("analytics-exports/")
    assert body["blob_path"].endswith(".json")
    assert body["size_bytes"] > 0

    saved_file = tmp_path / body["blob_path"]
    assert saved_file.is_file()
    parsed = json.loads(saved_file.read_text(encoding="utf-8"))
    assert "overview" in parsed
    assert "club_summaries" in parsed["overview"]


def test_club_logo_charter_and_event_poster_uploads(
    client, manager_token, sample_club, sample_event, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "AZURE_STORAGE_CONNECTION_STRING", "")
    headers = {"Authorization": f"Bearer {manager_token}"}

    # 1. Club logo PNG
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    logo_res = client.post(
        "/api/v1/uploads",
        headers=headers,
        files={"file": ("club_logo.png", io.BytesIO(png_bytes), "image/png")},
        data={"entity_type": "Clubs", "entity_id": sample_club.ClubId, "media_kind": "logo"},
    )
    assert logo_res.status_code == 201
    logo_data = logo_res.json()
    assert logo_data["media_kind"] == "logo"

    # 2. Club charter PDF
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    charter_res = client.post(
        "/api/v1/uploads",
        headers=headers,
        files={"file": ("charter.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"entity_type": "Clubs", "entity_id": sample_club.ClubId, "media_kind": "charter"},
    )
    assert charter_res.status_code == 201

    # 3. Event poster JPEG
    jpg_bytes = b"\xff\xd8\xff\xe0" + b"1" * 32
    poster_res = client.post(
        "/api/v1/uploads",
        headers=headers,
        files={"file": ("poster.jpg", io.BytesIO(jpg_bytes), "image/jpeg")},
        data={"entity_type": "Events", "entity_id": sample_event.EventId, "media_kind": "poster"},
    )
    assert poster_res.status_code == 201

    # Verify Club & Event APIs expose the attached media URLs
    club_detail = client.get(f"/api/v1/clubs/{sample_club.ClubId}").json()
    assert club_detail["logo_url"] == f"/api/v1/uploads/media/{logo_data['upload_id']}"
    assert club_detail["charter_pdf_url"] == f"/api/v1/uploads/media/{charter_res.json()['upload_id']}"

    ev_detail = client.get(f"/api/v1/events/{sample_event.EventId}").json()
    assert ev_detail["poster_url"] == f"/api/v1/uploads/media/{poster_res.json()['upload_id']}"

    # Verify public media endpoint serves active-club logo cleanly
    media_get = client.get(club_detail["logo_url"])
    assert media_get.status_code == 200
    assert media_get.content == png_bytes


def test_dedicated_club_media_and_event_banner_endpoints(
    client, manager_token, sample_club, sample_event, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "AZURE_STORAGE_CONNECTION_STRING", "")
    headers = {"Authorization": f"Bearer {manager_token}"}

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"M" * 32
    club_res = client.post(
        f"/api/v1/clubs/{sample_club.ClubId}/media",
        headers=headers,
        files={"file": ("emblem.png", io.BytesIO(png_bytes), "image/png")},
        data={"media_kind": "logo"},
    )
    assert club_res.status_code == 201
    assert club_res.json()["entity_type"] == "Clubs"
    assert club_res.json()["media_kind"] == "logo"

    jpg_bytes = b"\xff\xd8\xff\xe0" + b"B" * 32
    event_res = client.post(
        f"/api/v1/events/{sample_event.EventId}/banner",
        headers=headers,
        files={"file": ("banner.jpg", io.BytesIO(jpg_bytes), "image/jpeg")},
    )
    assert event_res.status_code == 201
    assert event_res.json()["entity_type"] == "Events"
    assert event_res.json()["media_kind"] == "poster"

    # Banner endpoint must reject non-image files (e.g. PDF)
    pdf_bytes = b"%PDF-1.4\n%%EOF\n"
    bad_banner = client.post(
        f"/api/v1/events/{sample_event.EventId}/banner",
        headers=headers,
        files={"file": ("bad.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert bad_banner.status_code == 400

    # Verify leadership_count is surfaced cleanly in analytics view
    club_detail = client.get(f"/api/v1/clubs/{sample_club.ClubId}").json()
    assert club_detail["logo_url"] == f"/api/v1/uploads/media/{club_res.json()['upload_id']}"
    ev_detail = client.get(f"/api/v1/events/{sample_event.EventId}").json()
    assert ev_detail["poster_url"] == f"/api/v1/uploads/media/{event_res.json()['upload_id']}"


def test_pymssql_url_strips_odbc_and_postgres_query_params():
    from app.db.session import normalize_sync_database_url

    cleaned = normalize_sync_database_url(
        "mssql+pymssql://clubsphereadmin:pw@clubsphere-sql-srv.database.windows.net:1433/clubspheredb"
        "?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&sslmode=require"
    )
    assert "driver=" not in cleaned
    assert "Encrypt=" not in cleaned
    assert "sslmode=" not in cleaned
    assert cleaned.endswith("/clubspheredb")


def test_unsafe_media_url_is_rejected(client, manager_token, sample_club):
    res = client.put(
        f"/api/v1/clubs/{sample_club.ClubId}",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"logo_url": "javascript:alert(1)"},
    )
    assert res.status_code == 422


def test_azure_blob_storage_service_virtual_folders(monkeypatch):
    assert blob_key_for_entity("id1", "crest.png", "Clubs", 7, "logo", "image/png") == "clubs/7/logos/id1_crest.png"
    assert blob_key_for_entity("id2", "doc.pdf", "Clubs", 7, "charter", "application/pdf") == "clubs/7/charters/id2_doc.pdf"
    assert blob_key_for_entity("id3", "flyer.jpg", "Events", 12, "poster", "image/jpeg") == "events/12/posters/id3_flyer.jpg"

    mock_blob_client = MagicMock()
    mock_blob_client.url = "https://csacct.blob.core.windows.net/clubsphere-media/clubs/7/logos/id1_crest.png"
    mock_blob_client.get_blob_properties.return_value = MagicMock(size=12)
    mock_blob_client.download_blob.return_value.readall.return_value = b"blob-content"

    mock_container = MagicMock()
    mock_container.exists.return_value = True
    mock_container.get_blob_client.return_value = mock_blob_client

    mock_service = MagicMock()
    mock_service.get_container_client.return_value = mock_container

    import azure.storage.blob as az_blob
    monkeypatch.setattr(az_blob.BlobServiceClient, "from_connection_string", MagicMock(return_value=mock_service))
    monkeypatch.setattr(settings, "AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=csacct;AccountKey=abc==;EndpointSuffix=core.windows.net")
    monkeypatch.setattr(settings, "AZURE_STORAGE_CONTAINER_NAME", "clubsphere-media")
    monkeypatch.setattr(settings, "AZURE_STORAGE_USE_EMULATOR", False)

    url = store_blob_or_local(
        b"blob-content",
        "id1",
        "crest.png",
        entity_type="Clubs",
        entity_id=7,
        media_kind="logo",
        content_type="image/png",
    )
    assert url == mock_blob_client.url
    mock_container.get_blob_client.assert_called_with("clubs/7/logos/id1_crest.png")

    downloaded = read_stored_bytes(url)
    assert downloaded == b"blob-content"


def test_neon_to_azure_sql_migration_is_idempotent(tmp_path):
    src_engine = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst_engine = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    Base.metadata.create_all(bind=src_engine)

    from sqlalchemy.orm import sessionmaker
    SrcSession = sessionmaker(bind=src_engine)
    db = SrcSession()
    try:
        role = Role(RoleName=RoleNameEnum.CLUB_MANAGER.value)
        branch = Branch(BranchKey="btech", Name="B.Tech", DegreeLevel="undergraduate", SortOrder=0)
        db.add_all([role, branch])
        db.flush()
        prog = Program(
            ProgramKey="btech_cse", BranchId=branch.BranchId, Name="CSE", FullName="B.Tech - CSE", SortOrder=0
        )
        db.add(prog)
        db.flush()
        user = User(
            Email="lead@clubsphere.edu",
            PasswordHash=get_password_hash("Password@123"),
            FullName="Lead User",
            RoleId=role.RoleId,
            ProgramId=prog.ProgramId,
            IsActive=True,
        )
        db.add(user)
        db.flush()
        club = Club(
            Name="AI Pioneers",
            ProgramId=prog.ProgramId,
            ManagerUserId=user.UserId,
            Description="Research & builders",
            PastAchievements=[{"title": "SIH Winner", "description": "1st place"}],
            LeadershipContacts=[{"role": "President", "name": "Lead User", "email": "lead@clubsphere.edu"}],
            Status="active",
        )
        db.add(club)
        db.flush()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        ev = Event(
            ClubId=club.ClubId,
            Title="ML Summit",
            VenueText="Auditorium",
            EventDate=now + timedelta(days=5),
            RegistrationDeadline=now + timedelta(days=3),
            Capacity=100,
            Status="published",
            CreatedByUserId=user.UserId,
        )
        db.add(ev)
        db.flush()
        db.add(ClubMembership(ClubId=club.ClubId, UserId=user.UserId, Status="active", Role="Lead"))
        db.add(EventRegistration(EventId=ev.EventId, UserId=user.UserId, Status="confirmed"))
        db.commit()
    finally:
        db.close()

    # Check identity PK helper accurately distinguishes int IDENTITY tables vs string PK tables
    assert table_has_identity_pk(Base.metadata.tables["Clubs"]) is True
    assert table_has_identity_pk(Base.metadata.tables["UploadedFiles"]) is False

    first_run = migrate_databases(src_engine, dst_engine, stamp_alembic=True)
    assert all(row["exact_match"] for row in first_run)
    clubs_row = next(r for r in first_run if r["table"] == "Clubs")
    assert clubs_row["source_count"] == 1
    assert clubs_row["inserted"] == 1

    # Re-run must be 100% idempotent with zero duplicate inserts
    second_run = migrate_databases(src_engine, dst_engine, stamp_alembic=True)
    assert all(row["exact_match"] for row in second_run)
    assert all(row["inserted"] == 0 for row in second_run)

    # Verify CLI supports --source-url and --target-url flags directly
    from scripts.migrate_neon_to_azure_sql import main as migrate_cli_main
    rc = migrate_cli_main([
        "--source-url", f"sqlite:///{tmp_path / 'src.db'}",
        "--target-url", f"sqlite:///{tmp_path / 'dst2.db'}",
    ])
    # note: file-based sqlite URL is allowed in direct engine tests above; let's assert CLI works cleanly with memory/env or mock
    assert rc == 0

    src_engine.dispose()
    dst_engine.dispose()
