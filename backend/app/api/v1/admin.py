from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.audit import record_audit_log
from app.core.authorization import branch_id_for_user, is_hod
from app.core.database import get_db, escape_like
from app.core.rate_limit import utc_now_naive
from app.core.rbac import require_roles, RoleNameEnum
from app.models.models import (
    Club,
    ClubProposal,
    Event,
    EventRegistration,
    Attendance,
    Branch,
    Program,
    RefreshSession,
    Role,
    User,
    AuditLog,
)
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    BranchMetricItem,
)
from app.schemas.audit import (
    AuditLogResponse,
    AuditLogListResponse,
)
from app.schemas.auth import (
    UserResponse,
    UserRoleUpdateRequest,
    UserAdminListResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin & Analytics"])


@router.get("/analytics/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    current_user: User = Depends(require_roles(RoleNameEnum.ADMINISTRATOR.value, RoleNameEnum.HOD.value)),
    db: Session = Depends(get_db),
):
    """Retrieve analytics calculated from actual database records.

    Administrators see institution-wide figures. HODs are restricted to their
    own academic branch so analytics cannot be used to inspect another branch.
    """
    hod_scope = is_hod(current_user)
    scoped_branch_id = branch_id_for_user(current_user) if hod_scope else None

    def club_query():
        query = db.query(Club)
        if hod_scope:
            if scoped_branch_id is None:
                return query.filter(Club.ClubId == -1)
            query = query.join(Program, Club.ProgramId == Program.ProgramId).filter(
                Program.BranchId == scoped_branch_id
            )
        return query

    def event_query():
        query = db.query(Event)
        if hod_scope:
            if scoped_branch_id is None:
                return query.filter(Event.EventId == -1)
            query = (
                query.join(Club, Event.ClubId == Club.ClubId)
                .join(Program, Club.ProgramId == Program.ProgramId)
                .filter(Program.BranchId == scoped_branch_id)
            )
        return query

    def registration_query():
        query = db.query(EventRegistration)
        if hod_scope:
            if scoped_branch_id is None:
                return query.filter(EventRegistration.RegistrationId == -1)
            query = (
                query.join(Event, EventRegistration.EventId == Event.EventId)
                .join(Club, Event.ClubId == Club.ClubId)
                .join(Program, Club.ProgramId == Program.ProgramId)
                .filter(Program.BranchId == scoped_branch_id)
            )
        return query

    def attendance_query():
        query = db.query(Attendance)
        if hod_scope:
            if scoped_branch_id is None:
                return query.filter(Attendance.AttendanceId == -1)
            query = (
                query.join(Event, Attendance.EventId == Event.EventId)
                .join(Club, Event.ClubId == Club.ClubId)
                .join(Program, Club.ProgramId == Program.ProgramId)
                .filter(Program.BranchId == scoped_branch_id)
            )
        return query

    total_clubs = club_query().with_entities(func.count(Club.ClubId)).scalar() or 0
    active_clubs = club_query().filter(Club.Status == "active").with_entities(
        func.count(Club.ClubId)
    ).scalar() or 0

    pending_proposals_query = db.query(ClubProposal).filter(
        ClubProposal.Status.in_(["submitted", "changes_requested"])
    )
    if hod_scope:
        if scoped_branch_id is None:
            pending_proposals_query = pending_proposals_query.filter(
                ClubProposal.ProposalId == -1
            )
        else:
            pending_proposals_query = pending_proposals_query.join(
                Program, ClubProposal.ProgramId == Program.ProgramId
            ).filter(Program.BranchId == scoped_branch_id)
    pending_proposals = pending_proposals_query.with_entities(
        func.count(ClubProposal.ProposalId)
    ).scalar() or 0

    total_events = event_query().with_entities(func.count(Event.EventId)).scalar() or 0
    published_events = event_query().filter(Event.Status == "published").with_entities(
        func.count(Event.EventId)
    ).scalar() or 0

    total_registrations = registration_query().with_entities(
        func.count(EventRegistration.RegistrationId)
    ).scalar() or 0
    confirmed_registrations = registration_query().filter(
        EventRegistration.Status == "confirmed"
    ).with_entities(func.count(EventRegistration.RegistrationId)).scalar() or 0

    total_attendance = attendance_query().with_entities(
        func.count(Attendance.AttendanceId)
    ).scalar() or 0

    avg_attendance_rate = 0.0
    if confirmed_registrations > 0:
        avg_attendance_rate = round(total_attendance / confirmed_registrations, 4)

    student_query = db.query(User).join(
        Role, User.RoleId == Role.RoleId
    ).filter(Role.RoleName == RoleNameEnum.STUDENT.value)
    if hod_scope:
        if scoped_branch_id is None:
            student_query = student_query.filter(User.UserId == -1)
        else:
            student_query = student_query.join(
                Program, User.ProgramId == Program.ProgramId
            ).filter(Program.BranchId == scoped_branch_id)
    total_students = student_query.with_entities(func.count(User.UserId)).scalar() or 0

    # Branch breakdown. HODs only receive their own branch's metrics.
    branches_query = db.query(Branch)
    if hod_scope:
        if scoped_branch_id is None:
            branches_query = branches_query.filter(Branch.BranchId == -1)
        else:
            branches_query = branches_query.filter(Branch.BranchId == scoped_branch_id)
    branches = branches_query.all()
    branch_metrics: List[BranchMetricItem] = []

    for b in branches:
        b_active_clubs = (
            db.query(func.count(Club.ClubId))
            .join(Program, Club.ProgramId == Program.ProgramId)
            .filter(Program.BranchId == b.BranchId, Club.Status == "active")
            .scalar()
            or 0
        )

        b_events = (
            db.query(func.count(Event.EventId))
            .join(Event.club)
            .join(Program, Club.ProgramId == Program.ProgramId)
            .filter(Program.BranchId == b.BranchId)
            .scalar()
            or 0
        )

        b_registrations = (
            db.query(func.count(EventRegistration.RegistrationId))
            .join(EventRegistration.event)
            .join(Event.club)
            .join(Program, Club.ProgramId == Program.ProgramId)
            .filter(Program.BranchId == b.BranchId)
            .scalar()
            or 0
        )

        branch_metrics.append(
            BranchMetricItem(
                branch_id=b.BranchId,
                branch_name=b.Name,
                active_clubs=b_active_clubs,
                events_hosted=b_events,
                total_registrations=b_registrations,
            )
        )

    return AnalyticsOverviewResponse(
        total_clubs=total_clubs,
        active_clubs=active_clubs,
        pending_proposals=pending_proposals,
        total_events=total_events,
        published_events=published_events,
        total_registrations=total_registrations,
        confirmed_registrations=confirmed_registrations,
        total_attendance=total_attendance,
        avg_attendance_rate=avg_attendance_rate,
        total_students=total_students,
        branch_metrics=branch_metrics,
        department_metrics=branch_metrics,
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    actor_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_roles(RoleNameEnum.ADMINISTRATOR.value)),
    db: Session = Depends(get_db),
):
    """Query immutable audit log of sensitive system operations. Restricted strictly to Administrator."""
    query = db.query(AuditLog)

    if actor_id:
        query = query.filter(AuditLog.ActorUserId == actor_id)
    if entity_type:
        query = query.filter(AuditLog.EntityType == entity_type)
    if from_date:
        query = query.filter(AuditLog.CreatedAt >= from_date)
    if to_date:
        query = query.filter(AuditLog.CreatedAt <= to_date)

    total = query.count()
    logs = query.order_by(AuditLog.CreatedAt.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [
        AuditLogResponse(
            audit_log_id=log.AuditLogId,
            actor_user_id=log.ActorUserId,
            actor_email=log.actor.Email if log.actor else None,
            actor_name=log.actor.FullName if log.actor else None,
            action=log.Action,
            entity_type=log.EntityType,
            entity_id=log.EntityId,
            details=log.Details,
            created_at=log.CreatedAt,
        )
        for log in logs
    ]

    return AuditLogListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/users", response_model=UserAdminListResponse)
def list_users(
    role_name: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_roles(RoleNameEnum.ADMINISTRATOR.value)),
    db: Session = Depends(get_db),
):
    """List university user accounts with their assigned roles. Restricted to Administrator."""
    query = db.query(User).join(Role, User.RoleId == Role.RoleId)

    if role_name:
        query = query.filter(Role.RoleName == role_name)
    if search:
        term = f"%{escape_like(search)}%"
        query = query.filter(
            (User.Email.ilike(term, escape="\\"))
            | (User.FullName.ilike(term, escape="\\"))
        )

    total = query.count()
    users = query.order_by(User.UserId.asc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [
        UserResponse(
            user_id=u.UserId,
            email=u.Email,
            full_name=u.FullName,
            role=u.role.RoleName if u.role else RoleNameEnum.STUDENT.value,
            program_id=u.ProgramId,
            program_name=u.program.FullName if u.program else None,
            branch_id=u.program.BranchId if u.program else None,
            branch_name=u.program.branch.Name if u.program else None,
            is_active=u.IsActive,
            created_at=u.CreatedAt,
        )
        for u in users
    ]

    return UserAdminListResponse(items=items, total=total, page=page, page_size=page_size)


@router.put("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    current_user: User = Depends(require_roles(RoleNameEnum.ADMINISTRATOR.value)),
    db: Session = Depends(get_db),
):
    """Update a user's system role. Restricted to Administrator.

    Security rules enforced:
    1. Administrators cannot modify their own role (prevents accidental lockout/self-privilege changes).
    2. The target role must exist in the Roles table.
    3. The target user's active sessions are immediately revoked and their TokenVersion is incremented,
       invalidating all current JWT access tokens and forcing re-authentication with the new role.
    4. An immutable audit log entry is recorded.
    """
    if current_user.UserId == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot modify their own role. Another administrator must perform this change.",
        )

    target_user = db.query(User).filter(User.UserId == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    target_role = db.query(Role).filter(Role.RoleName == payload.role_name).first()
    if not target_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{payload.role_name}' is not recognized in the system",
        )

    old_role_name = target_user.role.RoleName if target_user.role else "Unknown"
    target_user.RoleId = target_role.RoleId

    # Privilege change security: rotate/invalidate all existing tokens for target user
    target_user.TokenVersion += 1
    now = utc_now_naive()
    db.query(RefreshSession).filter(
        RefreshSession.UserId == target_user.UserId,
        RefreshSession.RevokedAt.is_(None),
    ).update({RefreshSession.RevokedAt: now}, synchronize_session=False)

    record_audit_log(
        db=db,
        actor_user_id=current_user.UserId,
        action="USER_ROLE_UPDATED",
        entity_type="Users",
        entity_id=target_user.UserId,
        details={
            "target_user_id": target_user.UserId,
            "target_email": target_user.Email,
            "old_role": old_role_name,
            "new_role": target_role.RoleName,
        },
    )

    db.commit()
    db.refresh(target_user)

    return UserResponse(
        user_id=target_user.UserId,
        email=target_user.Email,
        full_name=target_user.FullName,
        role=target_user.role.RoleName,
        program_id=target_user.ProgramId,
        program_name=target_user.program.FullName if target_user.program else None,
        branch_id=target_user.program.BranchId if target_user.program else None,
        branch_name=target_user.program.branch.Name if target_user.program else None,
        is_active=target_user.IsActive,
        created_at=target_user.CreatedAt,
    )
