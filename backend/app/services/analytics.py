"""Analytics aggregation and T-SQL Power BI view management helpers."""

from typing import List, Optional

from sqlalchemy import case, func, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.authorization import branch_id_for_user, is_hod
from app.models.models import (
    Attendance,
    Branch,
    Club,
    ClubMembership,
    ClubProposal,
    Event,
    EventRegistration,
    Program,
    Role,
    RoleNameEnum,
    User,
)
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    BranchMetricItem,
    ClubAnalyticsSummaryItem,
)

VW_CLUB_ANALYTICS_SUMMARY_SELECT = """
SELECT
    c."ClubId",
    c."Name" AS "ClubName",
    c."Status" AS "ClubStatus",
    p."ProgramId",
    p."FullName" AS "ProgramName",
    b."BranchId",
    b."Name" AS "BranchName",
    u."UserId" AS "ManagerUserId",
    u."FullName" AS "ManagerName",
    COUNT(DISTINCT CASE WHEN cm."Status" = 'active' THEN cm."MembershipId" END) AS "ActiveMembersCount",
    COUNT(DISTINCT CASE WHEN cm."Status" = 'requested' THEN cm."MembershipId" END) AS "PendingMembersCount",
    COUNT(DISTINCT CASE WHEN cm."Status" = 'removed' THEN cm."MembershipId" END) AS "RemovedMembersCount",
    COUNT(DISTINCT CASE WHEN cm."Status" = 'active' AND cm."Role" <> 'Member' THEN cm."MembershipId" END) AS "LeadershipCount",
    COUNT(DISTINCT e."EventId") AS "TotalEventsCount",
    COUNT(DISTINCT CASE WHEN e."Status" = 'published' THEN e."EventId" END) AS "PublishedEventsCount",
    COUNT(DISTINCT CASE WHEN e."Status" = 'completed' THEN e."EventId" END) AS "CompletedEventsCount",
    COUNT(DISTINCT CASE WHEN er."Status" = 'confirmed' THEN er."RegistrationId" END) AS "ConfirmedRegistrationsCount",
    COUNT(DISTINCT a."AttendanceId") AS "TotalAttendanceCount",
    MAX(cm."JoinedAt") AS "LatestMembershipActivityAt",
    MAX(e."EventDate") AS "LatestEventDate",
    c."CreatedAt" AS "ClubCreatedAt"
FROM "Clubs" c
INNER JOIN "Programs" p ON c."ProgramId" = p."ProgramId"
INNER JOIN "Branches" b ON p."BranchId" = b."BranchId"
INNER JOIN "Users" u ON c."ManagerUserId" = u."UserId"
LEFT JOIN "ClubMemberships" cm ON c."ClubId" = cm."ClubId"
LEFT JOIN "Events" e ON c."ClubId" = e."ClubId"
LEFT JOIN "EventRegistrations" er ON e."EventId" = er."EventId"
LEFT JOIN "Attendance" a ON e."EventId" = a."EventId"
GROUP BY
    c."ClubId",
    c."Name",
    c."Status",
    p."ProgramId",
    p."FullName",
    b."BranchId",
    b."Name",
    u."UserId",
    u."FullName",
    c."CreatedAt"
""".strip()


def ensure_media_columns(target_engine: Engine) -> None:
    """Idempotently add LogoUrl/CharterPdfUrl (Clubs) and PosterUrl (Events) when upgrading existing dev DBs."""
    dialect_name = target_engine.dialect.name
    col_type = "NVARCHAR(500)" if dialect_name == "mssql" else "VARCHAR(500)"

    insp = inspect(target_engine)
    stmts: list[str] = []
    if insp.has_table("Clubs"):
        club_cols = {c["name"] for c in insp.get_columns("Clubs")}
        if "LogoUrl" not in club_cols:
            stmts.append(f'ALTER TABLE "Clubs" ADD "LogoUrl" {col_type} NULL' if dialect_name == "mssql" else f'ALTER TABLE "Clubs" ADD COLUMN "LogoUrl" {col_type}')
        if "CharterPdfUrl" not in club_cols:
            stmts.append(f'ALTER TABLE "Clubs" ADD "CharterPdfUrl" {col_type} NULL' if dialect_name == "mssql" else f'ALTER TABLE "Clubs" ADD COLUMN "CharterPdfUrl" {col_type}')
    if insp.has_table("Events"):
        event_cols = {c["name"] for c in insp.get_columns("Events")}
        if "PosterUrl" not in event_cols:
            stmts.append(f'ALTER TABLE "Events" ADD "PosterUrl" {col_type} NULL' if dialect_name == "mssql" else f'ALTER TABLE "Events" ADD COLUMN "PosterUrl" {col_type}')

    if stmts:
        with target_engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))


def ensure_analytics_views(target_engine: Engine) -> None:
    """Idempotently create ``vw_club_analytics_summary`` on Azure SQL, PostgreSQL, or SQLite."""
    dialect_name = target_engine.dialect.name
    with target_engine.begin() as conn:
        if dialect_name == "mssql":
            conn.execute(
                text(f"CREATE OR ALTER VIEW vw_club_analytics_summary AS\n{VW_CLUB_ANALYTICS_SUMMARY_SELECT}")
            )
        elif dialect_name == "postgresql":
            conn.execute(
                text(f"CREATE OR REPLACE VIEW vw_club_analytics_summary AS\n{VW_CLUB_ANALYTICS_SUMMARY_SELECT}")
            )
        else:
            conn.execute(text("DROP VIEW IF EXISTS vw_club_analytics_summary"))
            conn.execute(
                text(f"CREATE VIEW vw_club_analytics_summary AS\n{VW_CLUB_ANALYTICS_SUMMARY_SELECT}")
            )


def get_club_analytics_summaries(
    db: Session,
    *,
    hod_scope: bool = False,
    scoped_branch_id: Optional[int] = None,
) -> List[ClubAnalyticsSummaryItem]:
    """Query ``vw_club_analytics_summary`` with clean ORM fallback if the view does not exist."""
    if hod_scope and scoped_branch_id is None:
        return []

    try:
        sql = 'SELECT * FROM vw_club_analytics_summary'
        params: dict = {}
        if hod_scope:
            sql += ' WHERE "BranchId" = :branch_id'
            params["branch_id"] = scoped_branch_id
        sql += ' ORDER BY "ActiveMembersCount" DESC, "ClubName" ASC'
        rows = db.execute(text(sql), params).mappings().all()
        return [
            ClubAnalyticsSummaryItem(
                club_id=row["ClubId"],
                club_name=row["ClubName"],
                club_status=row["ClubStatus"],
                program_id=row["ProgramId"],
                program_name=row["ProgramName"],
                branch_id=row["BranchId"],
                branch_name=row["BranchName"],
                manager_user_id=row["ManagerUserId"],
                manager_name=row["ManagerName"],
                active_members=int(row["ActiveMembersCount"] or 0),
                pending_members=int(row["PendingMembersCount"] or 0),
                removed_members=int(row["RemovedMembersCount"] or 0),
                leadership_count=int(row.get("LeadershipCount") or 0),
                total_events=int(row["TotalEventsCount"] or 0),
                published_events=int(row["PublishedEventsCount"] or 0),
                completed_events=int(row["CompletedEventsCount"] or 0),
                confirmed_registrations=int(row["ConfirmedRegistrationsCount"] or 0),
                total_attendance=int(row["TotalAttendanceCount"] or 0),
                latest_membership_activity_at=row["LatestMembershipActivityAt"],
                latest_event_date=row["LatestEventDate"],
                club_created_at=row["ClubCreatedAt"],
            )
            for row in rows
        ]
    except Exception:
        # Fallback ORM aggregation (e.g. unit test sessions initialized without Alembic views)
        pass

    active_cnt = func.count(
        func.distinct(case((ClubMembership.Status == "active", ClubMembership.MembershipId)))
    )
    pending_cnt = func.count(
        func.distinct(case((ClubMembership.Status == "requested", ClubMembership.MembershipId)))
    )
    removed_cnt = func.count(
        func.distinct(case((ClubMembership.Status == "removed", ClubMembership.MembershipId)))
    )
    leadership_cnt = func.count(
        func.distinct(
            case(
                (
                    (ClubMembership.Status == "active") & (ClubMembership.Role != "Member"),
                    ClubMembership.MembershipId,
                )
            )
        )
    )
    total_events_cnt = func.count(func.distinct(Event.EventId))
    published_events_cnt = func.count(
        func.distinct(case((Event.Status == "published", Event.EventId)))
    )
    completed_events_cnt = func.count(
        func.distinct(case((Event.Status == "completed", Event.EventId)))
    )
    confirmed_regs_cnt = func.count(
        func.distinct(case((EventRegistration.Status == "confirmed", EventRegistration.RegistrationId)))
    )
    attendance_cnt = func.count(func.distinct(Attendance.AttendanceId))

    query = (
        db.query(
            Club.ClubId,
            Club.Name,
            Club.Status,
            Program.ProgramId,
            Program.FullName,
            Branch.BranchId,
            Branch.Name,
            User.UserId,
            User.FullName,
            active_cnt,
            pending_cnt,
            removed_cnt,
            leadership_cnt,
            total_events_cnt,
            published_events_cnt,
            completed_events_cnt,
            confirmed_regs_cnt,
            attendance_cnt,
            func.max(ClubMembership.JoinedAt),
            func.max(Event.EventDate),
            Club.CreatedAt,
        )
        .join(Program, Club.ProgramId == Program.ProgramId)
        .join(Branch, Program.BranchId == Branch.BranchId)
        .join(User, Club.ManagerUserId == User.UserId)
        .outerjoin(ClubMembership, Club.ClubId == ClubMembership.ClubId)
        .outerjoin(Event, Club.ClubId == Event.ClubId)
        .outerjoin(EventRegistration, Event.EventId == EventRegistration.EventId)
        .outerjoin(Attendance, Event.EventId == Attendance.EventId)
    )
    if hod_scope:
        query = query.filter(Branch.BranchId == scoped_branch_id)

    rows = (
        query.group_by(
            Club.ClubId,
            Club.Name,
            Club.Status,
            Program.ProgramId,
            Program.FullName,
            Branch.BranchId,
            Branch.Name,
            User.UserId,
            User.FullName,
            Club.CreatedAt,
        )
        .order_by(active_cnt.desc(), Club.Name.asc())
        .all()
    )
    return [
        ClubAnalyticsSummaryItem(
            club_id=row[0],
            club_name=row[1],
            club_status=row[2],
            program_id=row[3],
            program_name=row[4],
            branch_id=row[5],
            branch_name=row[6],
            manager_user_id=row[7],
            manager_name=row[8],
            active_members=int(row[9] or 0),
            pending_members=int(row[10] or 0),
            removed_members=int(row[11] or 0),
            leadership_count=int(row[12] or 0),
            total_events=int(row[13] or 0),
            published_events=int(row[14] or 0),
            completed_events=int(row[15] or 0),
            confirmed_registrations=int(row[16] or 0),
            total_attendance=int(row[17] or 0),
            latest_membership_activity_at=row[18],
            latest_event_date=row[19],
            club_created_at=row[20],
        )
        for row in rows
    ]


def build_analytics_overview(current_user: User, db: Session) -> AnalyticsOverviewResponse:
    """Compute institutional or branch-scoped analytics from live database tables and views."""
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

    branches_query = db.query(Branch)
    if hod_scope:
        if scoped_branch_id is None:
            branches_query = branches_query.filter(Branch.BranchId == -1)
        else:
            branches_query = branches_query.filter(Branch.BranchId == scoped_branch_id)
    branches = branches_query.order_by(Branch.SortOrder.asc(), Branch.Name.asc()).all()
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

    club_summaries = get_club_analytics_summaries(
        db,
        hod_scope=hod_scope,
        scoped_branch_id=scoped_branch_id,
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
        club_summaries=club_summaries,
    )
