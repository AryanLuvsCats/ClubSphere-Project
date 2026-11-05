import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import (
    can_manage_club,
    can_manage_event,
    can_view_club,
    can_view_event,
    can_view_proposal,
    is_admin,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.rbac import get_current_active_user
from app.core.storage import (
    read_stored_bytes,
    sanitize_filename,
    store_blob_or_local,
    validate_upload_bytes,
)
from app.models.models import Club, ClubProposal, Event, UploadedFile, User
from app.schemas.upload import UploadResponse

router = APIRouter(prefix="/uploads", tags=["File Storage & Uploads"])

ALLOWED_ENTITY_TYPES = {"ClubProposals", "Clubs", "Events"}


def _resolve_upload_entity(
    db: Session,
    user: User,
    entity_type: str,
    entity_id: int,
):
    """Return the target entity after enforcing upload ownership/management."""
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported entity_type",
        )

    if entity_type == "ClubProposals":
        proposal = (
            db.query(ClubProposal)
            .filter(ClubProposal.ProposalId == entity_id)
            .first()
        )
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target proposal not found",
            )
        if not (is_admin(user) or proposal.ApplicantUserId == user.UserId):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to upload files for this proposal",
            )
        return proposal

    if entity_type == "Clubs":
        club = db.query(Club).filter(Club.ClubId == entity_id).first()
        if not club:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target club not found",
            )
        if not can_manage_club(user, club):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to upload files for this club",
            )
        return club

    event = db.query(Event).filter(Event.EventId == entity_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target event not found",
        )
    if not can_manage_event(user, event):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to upload files for this event",
        )
    return event


def _can_read_upload(db: Session, user: User, upload: UploadedFile) -> bool:
    if is_admin(user) or upload.OwnerUserId == user.UserId:
        return True
    if upload.EntityType == "ClubProposals":
        proposal = (
            db.query(ClubProposal)
            .filter(ClubProposal.ProposalId == upload.EntityId)
            .first()
        )
        return bool(proposal and can_view_proposal(user, proposal))
    if upload.EntityType == "Clubs":
        club = db.query(Club).filter(Club.ClubId == upload.EntityId).first()
        return bool(club and can_view_club(user, club))
    if upload.EntityType == "Events":
        event = db.query(Event).filter(Event.EventId == upload.EntityId).first()
        return bool(event and can_view_event(user, event))
    return False


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_or_media(
    file: UploadFile = File(...),
    entity_type: str = Form(
        ...,
        min_length=1,
        max_length=50,
        description="Target entity type: ClubProposals, Clubs, or Events",
    ),
    entity_id: int = Form(..., gt=0, description="Target entity ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Upload a proposal document, club logo, or event poster.

    The target entity must exist and the caller must own/manage it. File bytes
    are capped before being read into memory, and magic bytes must match the
    declared MIME type.
    """
    _resolve_upload_entity(db, current_user, entity_type, entity_id)

    max_size = settings.MAX_UPLOAD_SIZE_BYTES
    file_bytes = await file.read(max_size + 1)
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                "File exceeds maximum allowed size of "
                f"{max_size // (1024 * 1024)} MB"
            ),
        )

    sanitized_name = sanitize_filename(file.filename or "upload.bin")
    content_type, size_bytes = validate_upload_bytes(
        file.content_type or "",
        file_bytes,
        sanitized_name,
    )

    file_id = uuid.uuid4().hex
    storage_ref = store_blob_or_local(
        file_bytes=file_bytes,
        file_id=file_id,
        sanitized_name=sanitized_name,
    )

    db_file = UploadedFile(
        FileId=file_id,
        OwnerUserId=current_user.UserId,
        EntityType=entity_type,
        EntityId=entity_id,
        OriginalFilename=sanitized_name,
        BlobPath=storage_ref,
        MimeType=content_type,
        FileSizeBytes=size_bytes,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return UploadResponse(
        upload_id=db_file.FileId,
        original_filename=db_file.OriginalFilename,
        entity_type=db_file.EntityType,
        entity_id=db_file.EntityId,
        content_type=db_file.MimeType,
        size_bytes=db_file.FileSizeBytes,
        # Never return a filesystem path in the API response.
        url=f"{settings.API_V1_PREFIX}/uploads/{db_file.FileId}",
        created_at=db_file.CreatedAt,
    )


@router.get("/{upload_id}")
def download_uploaded_file(
    upload_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Download an uploaded file after checking entity-level authorization."""
    if not upload_id or len(upload_id) > 64:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    upload = db.query(UploadedFile).filter(UploadedFile.FileId == upload_id).first()
    if not upload or not _can_read_upload(db, current_user, upload):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    contents = read_stored_bytes(upload.BlobPath)
    safe_name = sanitize_filename(upload.OriginalFilename)

    return Response(
        content=contents,
        media_type=upload.MimeType,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(len(contents)),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
