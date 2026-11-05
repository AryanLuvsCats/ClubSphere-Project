from datetime import datetime
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.common import StrictRequestModel


class EventCreateRequest(StrictRequestModel):
    club_id: int = Field(..., gt=0)
    title: str = Field(..., min_length=2, max_length=200)
    venue_text: Optional[str] = Field(default=None, max_length=200)
    event_date: datetime
    registration_deadline: datetime
    capacity: int = Field(
        ...,
        gt=0,
        le=100000,
        description="Capacity must be greater than zero",
    )
    status: Optional[str] = Field(
        default="draft",
        pattern="^(draft|published|completed|cancelled)$",
    )

    @model_validator(mode="after")
    def validate_deadline_before_event(self) -> "EventCreateRequest":
        if self.registration_deadline > self.event_date:
            raise ValueError("Registration deadline must be earlier than or equal to the event date")
        return self


class EventUpdateRequest(StrictRequestModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    venue_text: Optional[str] = Field(default=None, max_length=200)
    event_date: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None
    capacity: Optional[int] = Field(default=None, gt=0, le=100000)
    status: Optional[str] = Field(
        default=None,
        pattern="^(draft|published|completed|cancelled)$",
    )

    @model_validator(mode="after")
    def validate_dates(self) -> "EventUpdateRequest":
        if self.event_date and self.registration_deadline:
            if self.registration_deadline > self.event_date:
                raise ValueError("Registration deadline must be earlier than or equal to the event date")
        return self


class EventResponse(StrictRequestModel):
    event_id: int
    club_id: int
    club_name: Optional[str] = None
    title: str
    venue_text: Optional[str] = None
    event_date: datetime
    registration_deadline: datetime
    capacity: int
    status: str
    created_by_user_id: int
    confirmed_registrations: int = 0
    seats_left: int = 0


class EventListResponse(StrictRequestModel):
    items: List[EventResponse]
    total: int
    page: int
    page_size: int


class RegistrationResponse(StrictRequestModel):
    registration_id: int
    event_id: int
    user_id: int
    status: str
    registered_at: datetime


class RegistrationRosterItem(StrictRequestModel):
    registration_id: int
    event_id: int
    user_id: int
    full_name: str
    email: str
    status: str
    registered_at: datetime
    attended: bool = False


class RegistrationListResponse(StrictRequestModel):
    items: List[RegistrationRosterItem]
    total: int
    page: int
    page_size: int


class AttendanceRecordRequest(StrictRequestModel):
    user_ids: List[int] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of user IDs to mark present",
    )

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, value: List[int]) -> List[int]:
        if any(user_id <= 0 for user_id in value):
            raise ValueError("user_ids must contain positive integers")
        return list(dict.fromkeys(value))


class AttendanceResponse(StrictRequestModel):
    event_id: int
    marked_present: int
    total_confirmed: int


class EventOutcomeCreateRequest(StrictRequestModel):
    summary: str = Field(..., min_length=5, max_length=5000)
    attendance_count_snapshot: Optional[int] = Field(default=None, ge=0, le=100000)


class EventOutcomeResponse(StrictRequestModel):
    outcome_id: int
    event_id: int
    summary: Optional[str] = None
    attendance_count_snapshot: int
    submitted_by_user_id: int
    submitted_at: datetime
