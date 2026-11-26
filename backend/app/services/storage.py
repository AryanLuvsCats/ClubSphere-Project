"""Azure Blob Storage and file-validation service for ClubSphere.

Handles:
- Unstructured media & document uploads (club logos, charter PDFs, event posters, proposals)
- Semi-structured analytics JSON exports under ``analytics-exports/``
- Azurite local emulator support (``AZURE_STORAGE_USE_EMULATOR``)
- Local development disk fallback (``local://<blob_key>``)
"""

import io
import json
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


LOCAL_STORAGE_SCHEME = "local://"
AZURITE_DEFAULT_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename so it cannot escape the upload directory."""
    basename = os.path.basename((filename or "").replace("\\", "/"))
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", basename)
    # Prevent hidden files and repeated dots.
    cleaned = cleaned.lstrip(".")
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    if not cleaned:
        cleaned = f"file_{uuid.uuid4().hex[:8]}"
    return cleaned[:180]


def _allowed_mime_types() -> list[str]:
    allowed = settings.ALLOWED_MIME_TYPES
    if isinstance(allowed, str):
        return [item.strip().lower() for item in allowed.split(",") if item.strip()]
    return [item.lower() for item in allowed]


def _detect_mime_type(data: bytes) -> Optional[str]:
    """Return the MIME type implied by magic bytes, or None if unrecognised."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"PK\x03\x04"):
        # A DOCX file is a ZIP container. Verify the expected OOXML members
        # instead of accepting arbitrary ZIP archives.
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" in names and any(
                    name.startswith("word/") for name in names
                ):
                    return (
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    )
        except (zipfile.BadZipFile, OSError):
            return None
    return None


def validate_upload_bytes(
    content_type: str,
    data: bytes,
    filename: str = "",
) -> Tuple[str, int]:
    """Validate declared MIME type, magic bytes, extension, and size."""
    allowed_list = _allowed_mime_types()
    declared = (content_type or "").lower().strip()
    if declared not in allowed_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Disallowed file type: {content_type}. Allowed types: {', '.join(allowed_list)}",
        )

    size_bytes = len(data)
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)",
        )
    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                "File exceeds maximum allowed size of "
                f"{settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB"
            ),
        )

    detected = _detect_mime_type(data)
    if detected is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match an allowed file format",
        )
    if detected != declared:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match the declared Content-Type",
        )

    safe_name = sanitize_filename(filename)
    extension = os.path.splitext(safe_name)[1].lower()
    allowed_extensions = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if extension and allowed_extensions.get(extension) != declared:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension does not match the declared Content-Type",
        )

    return detected, size_bytes


def validate_file(file: UploadFile) -> Tuple[str, int]:
    """Backward-compatible validator for callers that still pass an UploadFile."""
    max_size = settings.MAX_UPLOAD_SIZE_BYTES
    file.file.seek(0, os.SEEK_END)
    size_bytes = file.file.tell()
    file.file.seek(0)
    if size_bytes > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                "File exceeds maximum allowed size of "
                f"{max_size // (1024 * 1024)} MB"
            ),
        )
    data = file.file.read(max_size + 1)
    file.file.seek(0)
    return validate_upload_bytes(file.content_type or "", data, file.filename or "")


def blob_key_for_entity(
    file_id: str,
    sanitized_name: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    media_kind: Optional[str] = None,
    content_type: Optional[str] = None,
) -> str:
    """Build a virtual folder path inside the Azure Blob container."""
    leaf = f"{file_id}_{sanitized_name}"
    if entity_type == "Clubs" and entity_id is not None:
        is_pdf = (content_type or "").lower() == "application/pdf" or sanitized_name.lower().endswith(".pdf")
        folder = media_kind or ("charters" if is_pdf else "logos")
        if folder not in {"logos", "charters", "media"}:
            folder = "charters" if "charter" in folder else "logos"
        return f"clubs/{entity_id}/{folder}/{leaf}"
    if entity_type == "Events" and entity_id is not None:
        folder = media_kind or "posters"
        if folder not in {"posters", "media", "outcomes"}:
            folder = "posters"
        return f"events/{entity_id}/{folder}/{leaf}"
    if entity_type == "ClubProposals" and entity_id is not None:
        return f"proposals/{entity_id}/{leaf}"
    return leaf


def _resolve_azure_connection_string() -> Optional[str]:
    """Return active Azure Blob or Azurite connection string when configured."""
    conn_str = (settings.AZURE_STORAGE_CONNECTION_STRING or "").strip()
    if conn_str:
        if conn_str.lower().startswith("usedevelopmentstorage=true"):
            return AZURITE_DEFAULT_CONNECTION_STRING
        return conn_str
    if getattr(settings, "AZURE_STORAGE_USE_EMULATOR", False) and settings.ENVIRONMENT not in (
        "testing",
        "production",
        "staging",
    ):
        return AZURITE_DEFAULT_CONNECTION_STRING
    return None


def _upload_to_azure_blob(
    blob_name: str,
    payload: bytes,
    content_type: str,
    *,
    overwrite: bool = False,
) -> str:
    """Upload bytes to Azure Blob Storage / Azurite and return its canonical HTTPS/HTTP URL."""
    conn_str = _resolve_azure_connection_string()
    if not conn_str:
        raise RuntimeError("Azure Blob Storage connection string is not configured")

    from azure.storage.blob import BlobServiceClient, ContentSettings, PublicAccess

    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    container_client = blob_service_client.get_container_client(
        settings.AZURE_STORAGE_CONTAINER_NAME
    )
    if not container_client.exists():
        public_access = PublicAccess.Blob if getattr(settings, "AZURE_STORAGE_PUBLIC_READ", False) else None
        container_client.create_container(public_access=public_access)

    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        payload,
        overwrite=overwrite,
        content_settings=ContentSettings(content_type=content_type),
    )
    return blob_client.url


def _extract_blob_name_from_url(blob_url: str) -> str:
    """Extract container-relative blob key from a full Azure Blob or Azurite URL."""
    path = urlparse(blob_url).path.lstrip("/")
    container = (settings.AZURE_STORAGE_CONTAINER_NAME or "").strip("/")
    if container and f"{container}/" in path:
        return path.split(f"{container}/", 1)[1]
    parts = path.split("/", 1)
    if len(parts) == 2 and parts[1]:
        return parts[1]
    return os.path.basename(path)


def store_blob_or_local(
    file_bytes: bytes,
    file_id: str,
    sanitized_name: str,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    media_kind: Optional[str] = None,
    content_type: str = "application/octet-stream",
) -> str:
    """Store a file in Azure Blob Storage (or Azurite/local disk) and return its reference."""
    use_cloud_or_emulator = bool(
        settings.AZURE_STORAGE_CONNECTION_STRING
        or (
            getattr(settings, "AZURE_STORAGE_USE_EMULATOR", False)
            and settings.ENVIRONMENT not in ("testing", "production", "staging")
        )
    )
    blob_key = blob_key_for_entity(
        file_id=file_id,
        sanitized_name=sanitized_name,
        entity_type=entity_type,
        entity_id=entity_id,
        media_kind=media_kind,
        content_type=content_type,
    )

    if use_cloud_or_emulator:
        try:
            return _upload_to_azure_blob(
                blob_key,
                file_bytes,
                content_type=content_type,
                overwrite=False,
            )
        except Exception:
            if settings.ENVIRONMENT in ("production", "staging"):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Cloud storage service unavailable",
                )

    local_leaf = f"{file_id}_{sanitized_name}"
    upload_dir = os.path.abspath(settings.LOCAL_UPLOAD_DIR)
    os.makedirs(upload_dir, exist_ok=True)
    destination_path = os.path.join(upload_dir, local_leaf)
    if not os.path.abspath(destination_path).startswith(upload_dir + os.sep):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid storage path",
        )
    with open(destination_path, "wb") as handle:
        handle.write(file_bytes)
    return f"{LOCAL_STORAGE_SCHEME}{local_leaf}"


def store_analytics_json_export(
    payload: dict[str, Any],
    filename: Optional[str] = None,
) -> dict[str, Any]:
    """Serialize semi-structured analytics JSON to Azure Blob Storage under ``analytics-exports/``.

    Falls back cleanly to ``<LOCAL_UPLOAD_DIR>/analytics-exports/`` in offline local dev/testing.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = sanitize_filename(filename or f"clubsphere-analytics-{timestamp}.json")
    if not safe_name.lower().endswith(".json"):
        safe_name = f"{safe_name}.json"
    blob_key = f"analytics-exports/{safe_name}"
    serialized = json.dumps(payload, indent=2, default=str).encode("utf-8")

    conn_str = _resolve_azure_connection_string()
    if conn_str:
        try:
            blob_url = _upload_to_azure_blob(
                blob_key,
                serialized,
                content_type="application/json",
                overwrite=True,
            )
            return {
                "storage_backend": "azure_blob",
                "container": settings.AZURE_STORAGE_CONTAINER_NAME,
                "blob_path": blob_key,
                "blob_url": blob_url,
                "size_bytes": len(serialized),
            }
        except Exception:
            if settings.ENVIRONMENT in ("production", "staging"):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Cloud storage service unavailable for analytics export",
                )

    upload_dir = os.path.abspath(os.path.join(settings.LOCAL_UPLOAD_DIR, "analytics-exports"))
    os.makedirs(upload_dir, exist_ok=True)
    destination_path = os.path.abspath(os.path.join(upload_dir, safe_name))
    if not destination_path.startswith(upload_dir + os.sep):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid analytics export path",
        )
    with open(destination_path, "wb") as handle:
        handle.write(serialized)

    return {
        "storage_backend": "local",
        "container": settings.AZURE_STORAGE_CONTAINER_NAME,
        "blob_path": blob_key,
        "blob_url": f"{LOCAL_STORAGE_SCHEME}{blob_key}",
        "size_bytes": len(serialized),
    }


def read_stored_bytes(blob_path: str) -> bytes:
    """Read a stored file from Azure Blob Storage / Azurite or local upload storage."""
    max_size = settings.MAX_UPLOAD_SIZE_BYTES

    if blob_path.startswith(("http://", "https://")):
        conn_str = _resolve_azure_connection_string()
        if not conn_str:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File is not available",
            )
        try:
            from azure.storage.blob import BlobServiceClient

            blob_name = _extract_blob_name_from_url(blob_path)
            if not blob_name:
                raise ValueError("missing blob name")
            service = BlobServiceClient.from_connection_string(conn_str)
            container = service.get_container_client(
                settings.AZURE_STORAGE_CONTAINER_NAME
            )
            blob = container.get_blob_client(blob_name)
            properties = blob.get_blob_properties()
            if properties.size and properties.size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Stored file is too large to download",
                )
            return blob.download_blob().readall()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File is not available",
            )

    raw_name = blob_path
    if raw_name.startswith(LOCAL_STORAGE_SCHEME):
        raw_name = raw_name[len(LOCAL_STORAGE_SCHEME):]
    safe_name = os.path.basename(raw_name.replace("\\", "/"))
    upload_dir = os.path.abspath(settings.LOCAL_UPLOAD_DIR)
    path = os.path.abspath(os.path.join(upload_dir, safe_name))
    if not path.startswith(upload_dir + os.sep) or not os.path.isfile(path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File is not available",
        )
    if os.path.getsize(path) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Stored file is too large to download",
        )
    with open(path, "rb") as handle:
        return handle.read(max_size + 1)
