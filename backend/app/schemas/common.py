from typing import Optional
from pydantic import BaseModel, ConfigDict


def validate_safe_media_url(value: Optional[str]) -> Optional[str]:
    """Allow only http(s) URLs or internal API upload paths to block javascript:/data: XSS."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    lower = cleaned.lower()
    if lower.startswith(("https://", "http://", "/api/v1/uploads/")):
        return cleaned
    raise ValueError("Media URL must use https://, http://, or /api/v1/uploads/...")


class StrictRequestModel(BaseModel):
    """Base for request bodies: reject unknown fields and strip whitespace."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )
