from typing import Literal, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.authorization import can_view_club, is_admin, role_name
from app.core.database import (
    case_insensitive_equals,
    case_insensitive_like,
    escape_like,
    get_db,
)
from app.core.rbac import (
    check_club_ownership,
    get_current_active_user,
    get_optional_current_user,
    normalize_role,
    require_roles,
    RoleNameEnum,
)
from app.core.audit import record_audit_log
from app.models.models import (
    Club,
    ClubMembership,
    Program,
    Role,
    User,
    Notification,
    Event,
)
from app.schemas.club import (
    ClubAchievement,
    ClubCoreMember,
    ClubRecentEvent,
    ClubDetailResponse,
    ClubCreateRequest,
    ClubUpdateRequest,
    ClubResponse,
    ClubListResponse,
    MembershipJoinResponse,
    MembershipUpdateRequest,
    MembershipMemberResponse,
    MembershipListResponse,
    MyMembershipStatusResponse,
    PendingRequestCountResponse,
    ClubLeadershipEntry,
    ClubUpcomingEvent,
    ClubPublicProfileResponse,
)
from app.schemas.upload import UploadResponse
from app.api.v1.uploads import process_entity_upload

router = APIRouter(prefix="/clubs", tags=["Clubs & Memberships"])


@router.get("", response_model=ClubListResponse)
def list_clubs(
    program_id: Optional[int] = Query(None, gt=0),
    branch_id: Optional[int] = Query(None, gt=0),
    status_filter: Optional[Literal["pending", "active", "suspended"]] = Query(
        None, alias="status"
    ),
    search: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """List clubs. Non-active records are only visible to their manager or an admin."""
    query = db.query(Club).join(Program, Club.ProgramId == Program.ProgramId)

    if program_id:
        query = query.filter(Club.ProgramId == program_id)
    if branch_id:
        query = query.filter(Program.BranchId == branch_id)
    if status_filter:
        if status_filter != "active":
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Authentication is required to view non-active clubs",
                )
            if not is_admin(current_user):
                query = query.filter(Club.ManagerUserId == current_user.UserId)
        query = query.filter(Club.Status == status_filter)
    else:
        query = query.filter(Club.Status == "active")

    if search:
        search_fmt = f"%{escape_like(search)}%"
        query = query.filter(
            case_insensitive_like(Club.Name, search_fmt)
            | case_insensitive_like(Club.Description, search_fmt)
        )

    total = query.count()
    clubs = query.order_by(Club.Name.asc()).offset((page - 1) * page_size).limit(page_size).all()

    # Batch query membership counts to eliminate N+1 round trips
    club_ids = [c.ClubId for c in clubs]
    counts_map = {}
    if club_ids:
        counts = (
            db.query(ClubMembership.ClubId, func.count(ClubMembership.MembershipId))
            .filter(
                ClubMembership.ClubId.in_(club_ids),
                ClubMembership.Status == "active",
            )
            .group_by(ClubMembership.ClubId)
            .all()
        )
        counts_map = dict(counts)

    items = []
    for c in clubs:
        member_cnt = counts_map.get(c.ClubId, 0)

        items.append(
            ClubResponse(
                club_id=c.ClubId,
                name=c.Name,
                program_id=c.ProgramId,
                program_name=c.program.FullName if c.program else None,
                branch_id=c.program.BranchId if c.program else None,
                branch_name=c.program.branch.Name if c.program else None,
                manager_user_id=c.ManagerUserId,
                manager_name=c.manager.FullName if c.manager else None,
                description=c.Description,
                logo_url=c.LogoUrl,
                charter_pdf_url=c.CharterPdfUrl,
                status=c.Status,
                created_at=c.CreatedAt,
                member_count=member_cnt,
            )
        )

    return ClubListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/my-memberships", response_model=list[MyMembershipStatusResponse])
def list_my_membership_statuses(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return the signed-in user's own membership states across clubs."""
    memberships = db.query(ClubMembership).filter(
        ClubMembership.UserId == current_user.UserId
    ).all()
    return [
        MyMembershipStatusResponse(club_id=item.ClubId, status=item.Status)
        for item in memberships
    ]


@router.get("/pending-request-count", response_model=PendingRequestCountResponse)
def get_pending_request_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return a manager's assigned-club count or the administrator's global count."""
    current_role = role_name(current_user)
    if current_role not in {RoleNameEnum.CLUB_MANAGER.value, RoleNameEnum.ADMINISTRATOR.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager access required")

    query = db.query(func.count(ClubMembership.MembershipId)).join(
        Club, ClubMembership.ClubId == Club.ClubId
    ).filter(ClubMembership.Status == "requested")
    if not is_admin(current_user):
        query = query.filter(Club.ManagerUserId == current_user.UserId)
    return PendingRequestCountResponse(count=query.scalar() or 0)


def _build_club_detail_response(club: Club, db: Session, member_cnt: int) -> ClubDetailResponse:
    recent_events_rows = (
        db.query(Event)
        .options(joinedload(Event.outcome))
        .filter(Event.ClubId == club.ClubId)
        .order_by(Event.EventDate.desc())
        .limit(10)
        .all()
    )
    recent_events = [
        ClubRecentEvent(
            event_id=ev.EventId,
            title=ev.Title,
            event_date=ev.EventDate,
            venue_text=ev.VenueText,
            description=ev.outcome.Summary if ev.outcome else None,
            status=ev.Status,
        )
        for ev in recent_events_rows
    ]

    core_members = []
    if club.LeadershipContacts and isinstance(club.LeadershipContacts, list) and len(club.LeadershipContacts) > 0:
        for c in club.LeadershipContacts:
            if isinstance(c, dict) and "name" in c and "role" in c:
                core_members.append(
                    ClubCoreMember(
                        role=c.get("role", "Lead"),
                        name=c.get("name", ""),
                        email=c.get("email", ""),
                        phone=c.get("phone"),
                    )
                )

    if not core_members:
        leader_memberships = (
            db.query(ClubMembership)
            .filter(
                ClubMembership.ClubId == club.ClubId,
                ClubMembership.Status == "active",
                ClubMembership.Role.in_(
                    ("President", "Vice President", "Media Head", "Tech Head", "Lead", "Coordinator")
                ),
            )
            .all()
        )
        for lm in leader_memberships:
            if lm.user:
                core_members.append(
                    ClubCoreMember(
                        role=lm.Role,
                        name=lm.user.FullName,
                        email=lm.user.Email,
                        phone=None,
                    )
                )
        if not core_members and club.manager:
            core_members.append(
                ClubCoreMember(
                    role="Club Manager",
                    name=club.manager.FullName,
                    email=club.manager.Email,
                    phone=None,
                )
            )

    past_achievements = []
    if club.PastAchievements and isinstance(club.PastAchievements, list):
        for ach in club.PastAchievements:
            if isinstance(ach, dict) and "title" in ach and "description" in ach:
                past_achievements.append(
                    ClubAchievement(
                        title=ach["title"],
                        date=ach.get("date"),
                        description=ach["description"],
                        award_or_highlight=ach.get("award_or_highlight"),
                    )
                )

    return ClubDetailResponse(
        club_id=club.ClubId,
        name=club.Name,
        program_id=club.ProgramId,
        program_name=club.program.FullName if club.program else None,
        branch_id=club.program.BranchId if club.program else None,
        branch_name=club.program.branch.Name if club.program else None,
        manager_user_id=club.ManagerUserId,
        manager_name=club.manager.FullName if club.manager else None,
        description=club.Description,
        logo_url=club.LogoUrl,
        charter_pdf_url=club.CharterPdfUrl,
        status=club.Status,
        created_at=club.CreatedAt,
        member_count=member_cnt,
        motives=club.Motives,
        past_achievements=past_achievements,
        recent_events=recent_events,
        core_members=core_members,
    )


@router.get("/{club_id}", response_model=ClubDetailResponse)
def get_club_details(
    club_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a club. Pending/suspended clubs are hidden from the public."""
    club = db.query(Club).filter(Club.ClubId == club_id).first()
    if not club or not can_view_club(current_user, club):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Club with ID {club_id} not found",
        )

    member_cnt = (
        db.query(func.count(ClubMembership.MembershipId))
        .filter(ClubMembership.ClubId == club.ClubId, ClubMembership.Status == "active")
        .scalar()
        or 0
    )

    return _build_club_detail_response(club, db, member_cnt)


@router.get("/{club_id}/public-profile", response_model=ClubPublicProfileResponse)
def get_club_public_profile(
    club_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Return public club details, leadership names, and upcoming published events."""
    club = db.query(Club).filter(Club.ClubId == club_id).first()
    if not club or not can_view_club(current_user, club):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Club with ID {club_id} not found")

    member_count = db.query(func.count(ClubMembership.MembershipId)).filter(
        ClubMembership.ClubId == club_id,
        ClubMembership.Status == "active",
    ).scalar() or 0

    leadership_roles = ("Lead", "Coordinator", "Technical Lead", "Secretary")
    leaders = (
        db.query(ClubMembership)
        .filter(
            ClubMembership.ClubId == club_id,
            ClubMembership.Status == "active",
            ClubMembership.Role.in_(leadership_roles),
        )
        .order_by(ClubMembership.Role.asc(), ClubMembership.JoinedAt.asc())
        .all()
    )
    convener = (
        db.query(ClubMembership)
        .filter(
            ClubMembership.ClubId == club_id,
            ClubMembership.Status == "active",
            ClubMembership.Role.in_(("Faculty Advisor", "Faculty")),
        )
        .first()
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    upcoming = (
        db.query(Event)
        .filter(
            Event.ClubId == club_id,
            Event.Status == "published",
            Event.EventDate >= now,
        )
        .order_by(Event.EventDate.asc())
        .limit(5)
        .all()
    )

    return ClubPublicProfileResponse(
        club_id=club.ClubId,
        name=club.Name,
        program_id=club.ProgramId,
        program_name=club.program.FullName if club.program else None,
        branch_id=club.program.BranchId if club.program else None,
        branch_name=club.program.branch.Name if club.program else None,
        manager_user_id=club.ManagerUserId,
        manager_name=club.manager.FullName if club.manager else None,
        description=club.Description,
        logo_url=club.LogoUrl,
        charter_pdf_url=club.CharterPdfUrl,
        status=club.Status,
        created_at=club.CreatedAt,
        member_count=member_count,
        faculty_convener=convener.user.FullName if convener and convener.user else None,
        leadership_roster=[
            ClubLeadershipEntry(full_name=member.user.FullName, role=member.Role)
            for member in leaders
            if member.user
        ],
        upcoming_events=[
            ClubUpcomingEvent(
                event_id=event.EventId,
                title=event.Title,
                event_date=event.EventDate,
                venue_text=event.VenueText,
            )
            for event in upcoming
        ],
    )


@router.post("", response_model=ClubResponse, status_code=status.HTTP_201_CREATED)
def create_club_admin_override(
    payload: ClubCreateRequest,
    current_user: User = Depends(require_roles(RoleNameEnum.ADMINISTRATOR.value)),
    db: Session = Depends(get_db),
):
    """Directly create an active club (Administrator override; regular flow is via proposals)."""
    existing = db.query(Club).filter(case_insensitive_equals(Club.Name, payload.name.strip())).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A club named '{payload.name}' already exists",
        )

    dept = db.query(Program).filter(Program.ProgramId == payload.program_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Program with ID {payload.program_id} not found",
        )

    mgr = db.query(User).filter(User.UserId == payload.manager_user_id).first()
    if not mgr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Manager user with ID {payload.manager_user_id} not found",
        )

    new_club = Club(
        Name=payload.name.strip(),
        ProgramId=payload.program_id,
        ManagerUserId=payload.manager_user_id,
        Description=payload.description,
        LogoUrl=payload.logo_url,
        CharterPdfUrl=payload.charter_pdf_url,
        Status=payload.status,
    )
    db.add(new_club)
    db.flush()

    # Automatically add manager as an active Lead member
    membership = ClubMembership(
        ClubId=new_club.ClubId,
        UserId=payload.manager_user_id,
        Status="active",
        Role="Lead",
    )
    db.add(membership)

    # Synchronous audit log
    record_audit_log(
        db=db,
        actor_user_id=current_user.UserId,
        action="CLUB_CREATED_DIRECT",
        entity_type="Clubs",
        entity_id=new_club.ClubId,
        details={"name": new_club.Name, "manager_user_id": payload.manager_user_id},
    )

    db.commit()
    db.refresh(new_club)

    return ClubResponse(
        club_id=new_club.ClubId,
        name=new_club.Name,
        program_id=new_club.ProgramId,
        program_name=dept.FullName,
        branch_id=dept.BranchId,
        branch_name=dept.branch.Name,
        manager_user_id=new_club.ManagerUserId,
        manager_name=mgr.FullName,
        description=new_club.Description,
        logo_url=new_club.LogoUrl,
        charter_pdf_url=new_club.CharterPdfUrl,
        status=new_club.Status,
        created_at=new_club.CreatedAt,
        member_count=1,
    )


@router.put("/{club_id}", response_model=ClubDetailResponse)
def update_club(
    club_id: int,
    payload: ClubUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update club profile or status. Restricted to Club Manager of this club or Administrator."""
    club = check_club_ownership(club_id=club_id, user=current_user, db=db)

    if payload.name and payload.name.strip() != club.Name:
        duplicate = db.query(Club).filter(
            case_insensitive_equals(Club.Name, payload.name.strip()),
            Club.ClubId != club_id
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A club named '{payload.name}' already exists",
            )
        club.Name = payload.name.strip()

    if payload.description is not None:
        club.Description = payload.description

    if payload.motives is not None:
        club.Motives = payload.motives

    if payload.logo_url is not None:
        club.LogoUrl = payload.logo_url

    if payload.charter_pdf_url is not None:
        club.CharterPdfUrl = payload.charter_pdf_url

    if payload.past_achievements is not None:
        club.PastAchievements = [a.model_dump() for a in payload.past_achievements]

    if payload.leadership_contacts is not None:
        club.LeadershipContacts = [c.model_dump() for c in payload.leadership_contacts]

    if payload.status:
        # Only Administrator can suspend or reactivate clubs
        user_role = normalize_role(current_user.role.RoleName if current_user.role else "")
        if payload.status != club.Status and user_role != RoleNameEnum.ADMINISTRATOR.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an Administrator can change club status",
            )
        club.Status = payload.status

    if payload.manager_user_id:
        user_role = normalize_role(current_user.role.RoleName if current_user.role else "")
        if user_role != RoleNameEnum.ADMINISTRATOR.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an Administrator can transfer club ownership",
            )
        new_mgr = db.query(User).filter(User.UserId == payload.manager_user_id).first()
        if not new_mgr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target manager user does not exist",
            )
        club.ManagerUserId = payload.manager_user_id

    record_audit_log(
        db=db,
        actor_user_id=current_user.UserId,
        action="CLUB_UPDATED",
        entity_type="Clubs",
        entity_id=club.ClubId,
        details={"name": club.Name, "status": club.Status},
    )

    db.commit()
    db.refresh(club)

    member_cnt = (
        db.query(func.count(ClubMembership.MembershipId))
        .filter(ClubMembership.ClubId == club.ClubId, ClubMembership.Status == "active")
        .scalar()
        or 0
    )

    return _build_club_detail_response(club, db, member_cnt)


@router.post("/{club_id}/join", response_model=MembershipJoinResponse, status_code=status.HTTP_201_CREATED)
def request_join_club(
    club_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Submit a membership request to join a club."""
    club = db.query(Club).filter(Club.ClubId == club_id).first()
    if not club or club.Status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Club not found or is currently not active",
        )

    existing = db.query(ClubMembership).filter(
        ClubMembership.ClubId == club_id,
        ClubMembership.UserId == current_user.UserId
    ).first()

    if existing:
        if existing.Status == "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You are already an active member of this club",
            )
        elif existing.Status == "requested":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted a pending membership request for this club",
            )
        else:
            # If previously removed, reinstate as requested
            existing.Status = "requested"
            db.commit()
            db.refresh(existing)
            return MembershipJoinResponse(
                membership_id=existing.MembershipId,
                club_id=existing.ClubId,
                user_id=existing.UserId,
                status=existing.Status,
                joined_at=existing.JoinedAt,
            )

    membership = ClubMembership(
        ClubId=club_id,
        UserId=current_user.UserId,
        Status="requested",
        Role="Member",
    )
    db.add(membership)
    db.flush()

    # Notify the club manager and assigned faculty advisors so the request is
    # visible to the university reviewers as well as the day-to-day manager.
    reviewer_ids = {club.ManagerUserId}
    faculty_advisors = db.query(ClubMembership.UserId).filter(
        ClubMembership.ClubId == club.ClubId,
        ClubMembership.Status == "active",
        ClubMembership.Role.in_(("Faculty Advisor", "Faculty")),
    ).all()
    reviewer_ids.update(user_id for (user_id,) in faculty_advisors)
    program_faculty = db.query(User.UserId).join(Role, User.RoleId == Role.RoleId).filter(
        User.ProgramId == club.ProgramId,
        Role.RoleName == RoleNameEnum.FACULTY.value,
    ).all()
    reviewer_ids.update(user_id for (user_id,) in program_faculty)
    for reviewer_id in reviewer_ids - {current_user.UserId}:
        db.add(Notification(
            UserId=reviewer_id,
            Type="MEMBERSHIP_REQUEST",
            Message=f"{current_user.FullName} submitted a membership request for {club.Name}.",
        ))

    db.commit()
    db.refresh(membership)

    return MembershipJoinResponse(
        membership_id=membership.MembershipId,
        club_id=membership.ClubId,
        user_id=membership.UserId,
        status=membership.Status,
        joined_at=membership.JoinedAt,
    )


@router.get("/{club_id}/members", response_model=MembershipListResponse)
def list_club_members(
    club_id: int,
    status_filter: Optional[Literal["requested", "active", "removed"]] = Query(
        None, alias="status"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List members and applicants for a club. Restricted to Club Manager or Administrator."""
    check_club_ownership(club_id=club_id, user=current_user, db=db)

    query = db.query(ClubMembership).filter(ClubMembership.ClubId == club_id)
    if status_filter:
        query = query.filter(ClubMembership.Status == status_filter)

    total = query.count()
    members = query.order_by(ClubMembership.JoinedAt.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [
        MembershipMemberResponse(
            membership_id=m.MembershipId,
            club_id=m.ClubId,
            user_id=m.UserId,
            full_name=m.user.FullName,
            email=m.user.Email,
            status=m.Status,
            role=m.Role,
            joined_at=m.JoinedAt,
        )
        for m in members
    ]

    return MembershipListResponse(items=items, total=total, page=page, page_size=page_size)


@router.put("/{club_id}/members/{membership_id}", response_model=MembershipMemberResponse)
def update_membership_status(
    club_id: int,
    membership_id: int,
    payload: MembershipUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Approve, reject, or update role of a club member. Restricted to Club Manager or Administrator."""
    club = check_club_ownership(club_id=club_id, user=current_user, db=db)

    membership = db.query(ClubMembership).filter(
        ClubMembership.MembershipId == membership_id,
        ClubMembership.ClubId == club_id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership record not found in this club",
        )

    if payload.status and payload.status != membership.Status:
        membership.Status = payload.status
        # Notify the student
        notif = Notification(
            UserId=membership.UserId,
            Type="MEMBERSHIP_STATUS_UPDATE",
            Message=f"Your membership request for '{club.Name}' has been updated to: {payload.status}.",
        )
        db.add(notif)

    if payload.role:
        membership.Role = payload.role

    record_audit_log(
        db=db,
        actor_user_id=current_user.UserId,
        action="MEMBERSHIP_UPDATED",
        entity_type="ClubMemberships",
        entity_id=membership.MembershipId,
        details={"status": membership.Status, "role": membership.Role, "user_id": membership.UserId},
    )

    db.commit()
    db.refresh(membership)

    return MembershipMemberResponse(
        membership_id=membership.MembershipId,
        club_id=membership.ClubId,
        user_id=membership.UserId,
        full_name=membership.user.FullName,
        email=membership.user.Email,
        status=membership.Status,
        role=membership.Role,
        joined_at=membership.JoinedAt,
    )


@router.post("/{club_id}/media", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_club_media(
    club_id: int,
    file: UploadFile = File(...),
    media_kind: Optional[str] = Form(
        default=None,
        description="Optional kind: logo (image) or charter (PDF)",
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Upload a club logo image or official charter PDF to Azure Blob Storage."""
    return await process_entity_upload(
        file=file,
        entity_type="Clubs",
        entity_id=club_id,
        media_kind=media_kind,
        current_user=current_user,
        db=db,
        allowed_mime_override={
            "image/jpeg",
            "image/png",
            "image/webp",
            "application/pdf",
        },
    )
