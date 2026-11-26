from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.audit import record_audit_log
from app.core.database import get_db, escape_like, case_insensitive_like
from app.core.rate_limit import utc_now_naive
from app.core.rbac import require_roles, RoleNameEnum
from app.models.models import (
    RefreshSession,
    Role,
    User,
    AuditLog,
)
from app.schemas.analytics import AnalyticsOverviewResponse
from app.schemas.audit import (
    AuditLogResponse,
    AuditLogListResponse,
)
from app.schemas.auth import (
    UserResponse,
    UserRoleUpdateRequest,
    UserAdminListResponse,
)
from app.services.analytics import build_analytics_overview

router = APIRouter(prefix="/admin", tags=["Admin & Analytics"])


@router.get("/analytics/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    current_user: User = Depends(require_roles(RoleNameEnum.ADMINISTRATOR.value, RoleNameEnum.HOD.value)),
    db: Session = Depends(get_db),
):
    """Retrieve analytics calculated from actual database records and reporting views."""
    return build_analytics_overview(current_user, db)


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
            case_insensitive_like(User.Email, term)
            | case_insensitive_like(User.FullName, term)
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
