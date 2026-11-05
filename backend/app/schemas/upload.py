from datetime import datetime

from app.schemas.common import StrictRequestModel


class UploadResponse(StrictRequestModel):
    upload_id: str
    original_filename: str
    entity_type: str
    entity_id: int
    content_type: str
    size_bytes: int
    url: str
    created_at: datetime
