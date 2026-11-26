from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class BranchMetricItem(BaseModel):
    branch_id: int
    branch_name: str
    active_clubs: int
    events_hosted: int
    total_registrations: int


class ClubAnalyticsSummaryItem(BaseModel):
    club_id: int
    club_name: str
    club_status: str
    program_id: int
    program_name: Optional[str] = None
    branch_id: int
    branch_name: str
    manager_user_id: int
    manager_name: Optional[str] = None
    active_members: int = 0
    pending_members: int = 0
    removed_members: int = 0
    leadership_count: int = 0
    total_events: int = 0
    published_events: int = 0
    completed_events: int = 0
    confirmed_registrations: int = 0
    total_attendance: int = 0
    latest_membership_activity_at: Optional[datetime] = None
    latest_event_date: Optional[datetime] = None
    club_created_at: Optional[datetime] = None


class AnalyticsOverviewResponse(BaseModel):
    total_clubs: int
    active_clubs: int
    pending_proposals: int
    total_events: int
    published_events: int
    total_registrations: int
    confirmed_registrations: int
    total_attendance: int
    avg_attendance_rate: float
    total_students: int
    branch_metrics: List[BranchMetricItem] = []
    department_metrics: List[BranchMetricItem] = []  # Backwards compatibility alias
    club_summaries: List[ClubAnalyticsSummaryItem] = []


class AnalyticsExportResponse(BaseModel):
    storage_backend: str
    container: str
    blob_path: str
    blob_url: str
    size_bytes: int
    exported_at: datetime
