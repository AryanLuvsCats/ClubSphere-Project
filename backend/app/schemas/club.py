from datetime import datetime
from typing import List, Optional

from pydantic import Field, field_validator

from app.schemas.common import StrictRequestModel, validate_safe_media_url


class ClubCreateRequest(StrictRequestModel):
    name: str = Field(..., min_length=2, max_length=150)
    program_id: int = Field(..., gt=0)
    manager_user_id: int = Field(..., gt=0)
    description: Optional[str] = Field(default=None, max_length=5000)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    charter_pdf_url: Optional[str] = Field(default=None, max_length=500)
    status: str = Field(default="active", pattern="^(pending|active|suspended)$")

    @field_validator("logo_url", "charter_pdf_url")
    @classmethod
    def check_media_urls(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_media_url(v)


class ClubAchievement(StrictRequestModel):
    title: str = Field(..., min_length=2, max_length=200)
    date: Optional[str] = Field(default=None, max_length=50)
    description: str = Field(..., max_length=2000)
    award_or_highlight: Optional[str] = Field(default=None, max_length=200)


class ClubCoreMember(StrictRequestModel):
    role: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=150)
    email: str = Field(..., min_length=3, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=50)


class ClubRecentEvent(StrictRequestModel):
    event_id: int
    title: str
    event_date: datetime
    venue_text: Optional[str] = None
    description: Optional[str] = None
    status: str


class ClubUpdateRequest(StrictRequestModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=5000)
    motives: Optional[str] = Field(default=None, max_length=10000)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    charter_pdf_url: Optional[str] = Field(default=None, max_length=500)
    past_achievements: Optional[List[ClubAchievement]] = None
    leadership_contacts: Optional[List[ClubCoreMember]] = None
    status: Optional[str] = Field(default=None, pattern="^(pending|active|suspended)$")
    manager_user_id: Optional[int] = Field(default=None, gt=0)

    @field_validator("logo_url", "charter_pdf_url")
    @classmethod
    def check_media_urls(cls, v: Optional[str]) -> Optional[str]:
        return validate_safe_media_url(v)


class ClubResponse(StrictRequestModel):
    club_id: int
    name: str
    program_id: int
    program_name: Optional[str] = None
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    manager_user_id: int
    manager_name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    charter_pdf_url: Optional[str] = None
    status: str
    created_at: datetime
    member_count: Optional[int] = 0


class ClubDetailResponse(ClubResponse):
    motives: Optional[str] = None
    past_achievements: List[ClubAchievement] = []
    recent_events: List[ClubRecentEvent] = []
    core_members: List[ClubCoreMember] = []


class ClubListResponse(StrictRequestModel):
    items: List[ClubResponse]
    total: int
    page: int
    page_size: int


class MyMembershipStatusResponse(StrictRequestModel):
    club_id: int
    status: str


class PendingRequestCountResponse(StrictRequestModel):
    count: int


class ClubLeadershipEntry(StrictRequestModel):
    full_name: str
    role: str


class ClubUpcomingEvent(StrictRequestModel):
    event_id: int
    title: str
    event_date: datetime
    venue_text: Optional[str] = None


class ClubPublicProfileResponse(ClubResponse):
    faculty_convener: Optional[str] = None
    leadership_roster: List[ClubLeadershipEntry] = Field(default_factory=list)
    upcoming_events: List[ClubUpcomingEvent] = Field(default_factory=list)


class MembershipJoinResponse(StrictRequestModel):
    membership_id: int
    club_id: int
    user_id: int
    status: str
    joined_at: datetime


class MembershipUpdateRequest(StrictRequestModel):
    status: Optional[str] = Field(default=None, pattern="^(requested|active|removed)$")
    role: Optional[str] = Field(
        default=None,
        pattern="^(Member|Lead|Coordinator|Technical Lead|Secretary|Faculty Advisor)$",
    )


class MembershipMemberResponse(StrictRequestModel):
    membership_id: int
    club_id: int
    user_id: int
    full_name: str
    email: str
    status: str
    role: str
    joined_at: datetime


class MembershipListResponse(StrictRequestModel):
    items: List[MembershipMemberResponse]
    total: int
    page: int
    page_size: int
