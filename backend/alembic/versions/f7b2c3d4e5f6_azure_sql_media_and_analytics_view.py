"""add Azure Blob media URL columns and Power BI T-SQL analytics view

Revision ID: f7b2c3d4e5f6
Revises: e6a1b2c3d4e5
Create Date: 2026-11-26 16:00:00.000000

Adds LogoUrl / CharterPdfUrl to Clubs, PosterUrl to Events, and creates the
vw_club_analytics_summary reporting view (plus Power BI summary views on Azure SQL).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


# revision identifiers, used by Alembic.
revision: str = "f7b2c3d4e5f6"
down_revision: Union[str, None] = "e6a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_VW_CLUB_ANALYTICS_SELECT = """
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


def upgrade() -> None:
    url_type = sa.String(length=500).with_variant(mssql.NVARCHAR(500), "mssql")
    bind = op.get_bind()

    # Safely inspect existing columns when running online so re-applying over an
    # AUTO_CREATE_SCHEMA-patched database never fails with DuplicateColumn.
    existing_club_cols: set[str] = set()
    existing_event_cols: set[str] = set()
    if not op.get_context().as_sql:
        inspector = sa.inspect(bind)
        if inspector.has_table("Clubs"):
            existing_club_cols = {col["name"] for col in inspector.get_columns("Clubs")}
        if inspector.has_table("Events"):
            existing_event_cols = {col["name"] for col in inspector.get_columns("Events")}

    if "LogoUrl" not in existing_club_cols:
        op.add_column("Clubs", sa.Column("LogoUrl", url_type, nullable=True))
    if "CharterPdfUrl" not in existing_club_cols:
        op.add_column("Clubs", sa.Column("CharterPdfUrl", url_type, nullable=True))
    if "PosterUrl" not in existing_event_cols:
        op.add_column("Events", sa.Column("PosterUrl", url_type, nullable=True))

    dialect = op.get_context().dialect.name
    if dialect == "mssql":
        op.execute(f"CREATE OR ALTER VIEW vw_club_analytics_summary AS\n{_VW_CLUB_ANALYTICS_SELECT}")
    elif dialect == "postgresql":
        op.execute(f"CREATE OR REPLACE VIEW vw_club_analytics_summary AS\n{_VW_CLUB_ANALYTICS_SELECT}")
    else:
        op.execute("DROP VIEW IF EXISTS vw_club_analytics_summary")
        op.execute(f"CREATE VIEW vw_club_analytics_summary AS\n{_VW_CLUB_ANALYTICS_SELECT}")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vw_club_analytics_summary")
    op.drop_column("Events", "PosterUrl")
    op.drop_column("Clubs", "CharterPdfUrl")
    op.drop_column("Clubs", "LogoUrl")
