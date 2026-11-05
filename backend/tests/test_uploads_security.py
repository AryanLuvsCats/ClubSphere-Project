import io
import uuid

from app.core.config import settings
from app.models.models import ClubProposal


def _make_student_proposal(db_session, student_user):
    proposal = ClubProposal(
        ApplicantUserId=student_user.UserId,
        ProposedName=f"Upload Test Club {uuid.uuid4().hex[:8]}",
        ProgramId=student_user.ProgramId,
        Description="A proposal used to test authorized file uploads.",
        Status="submitted",
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    return proposal


def test_upload_valid_file_success(client, student_token, student_user, db_session):
    proposal = _make_student_proposal(db_session, student_user)
    headers = {"Authorization": f"Bearer {student_token}"}
    file_content = b"%PDF-1.4 sample pdf content for club proposal"
    files = {"file": ("proposal_doc.pdf", io.BytesIO(file_content), "application/pdf")}
    data = {"entity_type": "ClubProposals", "entity_id": proposal.ProposalId}

    response = client.post("/api/v1/uploads", files=files, data=data, headers=headers)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["original_filename"] == "proposal_doc.pdf"
    assert res_data["content_type"] == "application/pdf"
    assert res_data["size_bytes"] == len(file_content)
    assert "upload_id" in res_data
    assert res_data["url"] == f"/api/v1/uploads/{res_data['upload_id']}"
    assert "\\" not in res_data["url"]
    assert "://" not in res_data["url"]

    download = client.get(res_data["url"], headers=headers)
    assert download.status_code == 200
    assert download.content == file_content
    assert "attachment" in download.headers["content-disposition"]


def test_upload_disallowed_mime_type_fails(client, student_token, student_user, db_session):
    proposal = _make_student_proposal(db_session, student_user)
    headers = {"Authorization": f"Bearer {student_token}"}
    file_content = b"MZ executable binary payload"
    files = {"file": ("malware.exe", io.BytesIO(file_content), "application/x-msdownload")}
    data = {"entity_type": "ClubProposals", "entity_id": proposal.ProposalId}

    response = client.post("/api/v1/uploads", files=files, data=data, headers=headers)
    assert response.status_code == 400
    assert "Disallowed file type" in response.json()["detail"]


def test_upload_magic_byte_mismatch_fails(client, student_token, student_user, db_session):
    proposal = _make_student_proposal(db_session, student_user)
    headers = {"Authorization": f"Bearer {student_token}"}
    # Declares PNG but contains PDF bytes.
    files = {
        "file": (
            "spoofed.png",
            io.BytesIO(b"%PDF-1.4 not really a png"),
            "image/png",
        )
    }
    data = {"entity_type": "ClubProposals", "entity_id": proposal.ProposalId}

    response = client.post("/api/v1/uploads", files=files, data=data, headers=headers)
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"].lower()


def test_upload_empty_file_fails(client, student_token, student_user, db_session):
    proposal = _make_student_proposal(db_session, student_user)
    headers = {"Authorization": f"Bearer {student_token}"}
    files = {"file": ("empty.png", io.BytesIO(b""), "image/png")}
    data = {"entity_type": "ClubProposals", "entity_id": proposal.ProposalId}

    response = client.post("/api/v1/uploads", files=files, data=data, headers=headers)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_filename_sanitization_prevents_path_traversal(
    client, student_token, student_user, db_session
):
    proposal = _make_student_proposal(db_session, student_user)
    headers = {"Authorization": f"Bearer {student_token}"}
    file_content = b"\x89PNG\r\n\x1a\n fake png data"
    # Attempt directory traversal attack in filename
    files = {"file": ("../../etc/passwd.png", io.BytesIO(file_content), "image/png")}
    data = {"entity_type": "ClubProposals", "entity_id": proposal.ProposalId}

    response = client.post("/api/v1/uploads", files=files, data=data, headers=headers)
    assert response.status_code == 201
    sanitized_name = response.json()["original_filename"]
    assert ".." not in sanitized_name
    assert "/" not in sanitized_name
    assert "\\" not in sanitized_name


def test_upload_oversized_file_fails(
    client, student_token, student_user, db_session, monkeypatch
):
    proposal = _make_student_proposal(db_session, student_user)
    headers = {"Authorization": f"Bearer {student_token}"}
    # Temporarily set max size to 50 bytes to test 413 without generating 10MB in test memory
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 50)

    file_content = b"A" * 100  # 100 bytes > 50 bytes limit
    files = {"file": ("large_image.png", io.BytesIO(file_content), "image/png")}
    data = {"entity_type": "ClubProposals", "entity_id": proposal.ProposalId}

    response = client.post("/api/v1/uploads", files=files, data=data, headers=headers)
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"].lower()


def test_upload_rejects_other_users_proposal(
    client, student2_token, student_user, db_session
):
    proposal = _make_student_proposal(db_session, student_user)
    headers = {"Authorization": f"Bearer {student2_token}"}
    files = {
        "file": (
            "proposal_doc.pdf",
            io.BytesIO(b"%PDF-1.4 sample pdf content"),
            "application/pdf",
        )
    }
    data = {"entity_type": "ClubProposals", "entity_id": proposal.ProposalId}

    response = client.post("/api/v1/uploads", files=files, data=data, headers=headers)
    assert response.status_code == 403


def test_upload_rejects_unknown_entity_type(client, student_token, student_user, db_session):
    proposal = _make_student_proposal(db_session, student_user)
    headers = {"Authorization": f"Bearer {student_token}"}
    files = {"file": ("photo.png", io.BytesIO(b"\x89PNG\r\n\x1a\n data"), "image/png")}
    data = {"entity_type": "Users", "entity_id": proposal.ProposalId}

    response = client.post("/api/v1/uploads", files=files, data=data, headers=headers)
    assert response.status_code == 400
    assert "entity_type" in response.json()["detail"]
