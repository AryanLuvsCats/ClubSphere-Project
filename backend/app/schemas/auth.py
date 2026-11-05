from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field, SecretStr, field_validator

from app.schemas.common import StrictRequestModel


class UserRegisterRequest(StrictRequestModel):
    email: EmailStr
    password: SecretStr = Field(
        ...,
        description="Password. Length is validated server-side against PASSWORD_MIN/MAX_LENGTH.",
    )
    full_name: str = Field(..., min_length=2, max_length=150)
    program_id: Optional[int] = Field(default=None, gt=0)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        cleaned = value.strip()
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in cleaned):
            raise ValueError("full_name must not contain control characters")
        if "<" in cleaned or ">" in cleaned:
            raise ValueError("full_name must not contain HTML markup")
        return cleaned


class UserLoginRequest(StrictRequestModel):
    email: EmailStr
    password: SecretStr


class TokenRefreshRequest(StrictRequestModel):
    """Deprecated body-based refresh contract.

    Refresh tokens are now accepted only from the HttpOnly cookie. This model is
    retained so old clients get a clear validation error instead of a crash.
    """

    refresh_token: str = Field(..., min_length=1, max_length=512)


class TokenResponse(StrictRequestModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    user_id: int
    full_name: str
    email: str


class UserBrief(StrictRequestModel):
    user_id: int
    email: str
    full_name: str
    role: str
    program_id: Optional[int] = None
    is_active: bool


class UserResponse(StrictRequestModel):
    user_id: int
    email: str
    full_name: str
    role: str
    program_id: Optional[int] = None
    program_name: Optional[str] = None
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    is_active: bool
    created_at: datetime


class UserRoleUpdateRequest(StrictRequestModel):
    role_name: str = Field(..., min_length=2, max_length=50)


class UserAdminListResponse(StrictRequestModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
