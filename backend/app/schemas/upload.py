from datetime import datetime
from typing import Optional

from app.schemas.common import StrictRequestModel


class UploadResponse(StrictRequestModel):
    upload_id: str
    original_filename: str
    entity_type: str
    entity_id: int
    media_kind: Optional[str] = None
    content_type: str
    size_bytes: int
    url: str
    blob_url: Optional[str] = None
    created_at: datetime
