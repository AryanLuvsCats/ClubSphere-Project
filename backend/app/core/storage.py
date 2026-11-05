import io
import os
import re
import uuid
import zipfile
from typing import Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


LOCAL_STORAGE_SCHEME = "local://"


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

    # Reject a mismatched executable-looking extension even when the MIME type
    # and magic bytes agree. This keeps dangerous files out of browser downloads.
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


def store_blob_or_local(
    file_bytes: bytes,
    file_id: str,
    sanitized_name: str,
) -> str:
    """Store a file and return an opaque storage reference.

    Local development uses ``local://<blob_name>`` rather than exposing an
    absolute filesystem path. Azure Blob Storage returns its normal URL.
    """
    blob_name = f"{file_id}_{sanitized_name}"

    if settings.AZURE_STORAGE_CONNECTION_STRING:
        try:
            from azure.storage.blob import BlobServiceClient

            blob_service_client = BlobServiceClient.from_connection_string(
                settings.AZURE_STORAGE_CONNECTION_STRING
            )
            container_client = blob_service_client.get_container_client(
                settings.AZURE_STORAGE_CONTAINER_NAME
            )
            if not container_client.exists():
                container_client.create_container()
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(file_bytes, overwrite=False)
            return blob_client.url
        except Exception:
            # Fall back to local storage when Azure is unreachable or
            # misconfigured. Do not log the exception: it may contain secrets.
            pass

    upload_dir = os.path.abspath(settings.LOCAL_UPLOAD_DIR)
    os.makedirs(upload_dir, exist_ok=True)
    destination_path = os.path.join(upload_dir, blob_name)
    # Defence in depth: the sanitized name cannot contain separators, but check
    # the resolved path stays inside the upload directory anyway.
    if not os.path.abspath(destination_path).startswith(upload_dir + os.sep):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid storage path",
        )
    with open(destination_path, "wb") as handle:
        handle.write(file_bytes)
    return f"{LOCAL_STORAGE_SCHEME}{blob_name}"


def read_stored_bytes(blob_path: str) -> bytes:
    """Read a stored file without allowing traversal outside the upload dir."""
    max_size = settings.MAX_UPLOAD_SIZE_BYTES

    if blob_path.startswith(("http://", "https://")):
        if not settings.AZURE_STORAGE_CONNECTION_STRING:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File is not available",
            )
        try:
            from azure.storage.blob import BlobServiceClient

            blob_name = os.path.basename(urlparse(blob_path).path)
            if not blob_name:
                raise ValueError("missing blob name")
            service = BlobServiceClient.from_connection_string(
                settings.AZURE_STORAGE_CONNECTION_STRING
            )
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
