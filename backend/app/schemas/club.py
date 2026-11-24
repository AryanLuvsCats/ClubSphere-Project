from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.schemas.common import StrictRequestModel


class ClubCreateRequest(StrictRequestModel):
    name: str = Field(..., min_length=2, max_length=150)
    program_id: int = Field(..., gt=0)
    manager_user_id: int = Field(..., gt=0)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: str = Field(default="active", pattern="^(pending|active|suspended)$")


class ClubUpdateRequest(StrictRequestModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[str] = Field(default=None, pattern="^(pending|active|suspended)$")
    manager_user_id: Optional[int] = Field(default=None, gt=0)


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
    status: str
    created_at: datetime
    member_count: Optional[int] = 0


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
