from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.authorization import branch_id_for_user, is_hod
from app.core.rbac import RoleNameEnum, require_roles
from app.db.session import get_db
from app.models.models import User
from app.schemas.analytics import (
    AnalyticsExportResponse,
    AnalyticsOverviewResponse,
    ClubAnalyticsSummaryItem,
)
from app.services.analytics import (
    build_analytics_overview,
    get_club_analytics_summaries,
)
from app.services.storage import store_analytics_json_export

router = APIRouter(prefix="/analytics", tags=["Analytics & Power BI Reporting"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    current_user: User = Depends(
        require_roles(RoleNameEnum.ADMINISTRATOR.value, RoleNameEnum.HOD.value)
    ),
    db: Session = Depends(get_db),
):
    """Read-only institutional or branch-scoped analytics overview for dashboards."""
    return build_analytics_overview(current_user, db)


@router.get("/clubs", response_model=List[ClubAnalyticsSummaryItem])
def get_club_analytics_view(
    current_user: User = Depends(
        require_roles(RoleNameEnum.ADMINISTRATOR.value, RoleNameEnum.HOD.value)
    ),
    db: Session = Depends(get_db),
):
    """Read per-club metrics directly from ``vw_club_analytics_summary``."""
    hod_scope = is_hod(current_user)
    scoped_branch_id = branch_id_for_user(current_user) if hod_scope else None
    return get_club_analytics_summaries(
        db,
        hod_scope=hod_scope,
        scoped_branch_id=scoped_branch_id,
    )


@router.post("/export", response_model=AnalyticsExportResponse)
def export_analytics_snapshot(
    current_user: User = Depends(
        require_roles(RoleNameEnum.ADMINISTRATOR.value, RoleNameEnum.HOD.value)
    ),
    db: Session = Depends(get_db),
):
    """Persist a semi-structured JSON analytics snapshot to Azure Blob Storage (``analytics-exports/``)."""
    overview = build_analytics_overview(current_user, db)
    now_utc = datetime.now(timezone.utc)
    payload = {
        "schema_version": "1.0",
        "exported_at": now_utc.isoformat(),
        "exported_by_user_id": current_user.UserId,
        "scope": "branch" if is_hod(current_user) else "institution",
        "overview": overview.model_dump(mode="json"),
    }
    meta = store_analytics_json_export(payload)
    return AnalyticsExportResponse(**meta, exported_at=now_utc)
