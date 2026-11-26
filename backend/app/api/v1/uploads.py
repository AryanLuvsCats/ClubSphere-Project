from typing import Optional
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import (
    PUBLIC_EVENT_STATUSES,
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
from app.models.models import Club, ClubProposal, Event, UploadedFile, User
from app.schemas.upload import UploadResponse
from app.services.storage import (
    read_stored_bytes,
    sanitize_filename,
    store_blob_or_local,
    validate_upload_bytes,
)

router = APIRouter(prefix="/uploads", tags=["File Storage & Uploads"])

ALLOWED_ENTITY_TYPES = {"ClubProposals", "Clubs", "Events"}
ALLOWED_MEDIA_KINDS = {"logo", "charter", "poster", "attachment"}


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


def _is_public_media_asset(db: Session, upload: UploadedFile) -> bool:
    """Allow anonymous image/PDF rendering only for active clubs and public events."""
    if upload.EntityType == "Clubs":
        club = db.query(Club).filter(Club.ClubId == upload.EntityId).first()
        return bool(club and club.Status == "active")
    if upload.EntityType == "Events":
        event = db.query(Event).filter(Event.EventId == upload.EntityId).first()
        return bool(
            event
            and event.Status in PUBLIC_EVENT_STATUSES
            and (event.club is None or event.club.Status == "active")
        )
    return False


async def process_entity_upload(
    *,
    file: UploadFile,
    entity_type: str,
    entity_id: int,
    media_kind: Optional[str],
    current_user: User,
    db: Session,
    allowed_mime_override: Optional[set[str]] = None,
) -> UploadResponse:
    """Shared validation, Azure Blob storage upload, and entity URL persistence."""
    normalized_kind = media_kind.strip().lower() if media_kind else None
    if normalized_kind and normalized_kind not in ALLOWED_MEDIA_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported media_kind. Allowed values: {', '.join(sorted(ALLOWED_MEDIA_KINDS))}",
        )

    target_entity = _resolve_upload_entity(db, current_user, entity_type, entity_id)

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
    if allowed_mime_override and content_type not in allowed_mime_override:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Disallowed file type for this endpoint: {content_type}",
        )

    file_id = uuid.uuid4().hex
    storage_ref = store_blob_or_local(
        file_bytes=file_bytes,
        file_id=file_id,
        sanitized_name=sanitized_name,
        entity_type=entity_type,
        entity_id=entity_id,
        media_kind=normalized_kind,
        content_type=content_type,
    )

    is_remote_blob = storage_ref.startswith(("http://", "https://"))
    resolved_render_url = (
        storage_ref
        if is_remote_blob
        else f"{settings.API_V1_PREFIX}/uploads/media/{file_id}"
    )

    resolved_kind = normalized_kind
    if entity_type == "Clubs":
        if resolved_kind == "charter" or (
            resolved_kind is None and content_type == "application/pdf"
        ):
            target_entity.CharterPdfUrl = resolved_render_url
            resolved_kind = resolved_kind or "charter"
        elif resolved_kind == "logo" or (
            resolved_kind is None and content_type.startswith("image/")
        ):
            target_entity.LogoUrl = resolved_render_url
            resolved_kind = resolved_kind or "logo"
    elif entity_type == "Events":
        if resolved_kind == "poster" or (
            resolved_kind is None and content_type.startswith("image/")
        ):
            target_entity.PosterUrl = resolved_render_url
            resolved_kind = resolved_kind or "poster"

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
        media_kind=resolved_kind,
        content_type=db_file.MimeType,
        size_bytes=db_file.FileSizeBytes,
        url=f"{settings.API_V1_PREFIX}/uploads/{db_file.FileId}",
        blob_url=storage_ref if is_remote_blob else None,
        created_at=db_file.CreatedAt,
    )


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
    media_kind: Optional[str] = Form(
        default=None,
        description="Optional classification: logo, charter, poster, or attachment",
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Upload a proposal document, club logo, charter PDF, or event poster to Azure Blob Storage."""
    return await process_entity_upload(
        file=file,
        entity_type=entity_type,
        entity_id=entity_id,
        media_kind=media_kind,
        current_user=current_user,
        db=db,
    )


@router.get("/media/{upload_id}")
def serve_public_media_asset(
    upload_id: str,
    db: Session = Depends(get_db),
):
    """Serve public club logos, charters, and event posters for <img> rendering."""
    if not upload_id or len(upload_id) > 64:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found",
        )

    upload = db.query(UploadedFile).filter(UploadedFile.FileId == upload_id).first()
    if not upload or not _is_public_media_asset(db, upload):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found",
        )

    contents = read_stored_bytes(upload.BlobPath)
    safe_name = sanitize_filename(upload.OriginalFilename)

    return Response(
        content=contents,
        media_type=upload.MimeType,
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Content-Length": str(len(contents)),
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
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
