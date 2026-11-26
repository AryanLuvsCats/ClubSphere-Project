import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Identity,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.types import (
    TSQLDateTime,
    TSQLJson,
    TSQLText,
    TSQLUnicode,
    utcnow_sql,
)


def utc_now() -> datetime:
    """Return naive UTC timestamp compatible with T-SQL DATETIME2, PostgreSQL, and SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RoleNameEnum(str, enum.Enum):
    STUDENT = "Student"
    CLUB_MANAGER = "Club Manager"
    FACULTY = "Faculty"
    HOD = "HOD"
    ADMINISTRATOR = "Administrator"


class Branch(Base):
    """A top-level academic track, e.g. 'B.Tech', 'M.Tech', 'MBA'.

    Parent of :class:`Program`. Seeded from ``app/data/branches.json``.
    """

    __tablename__ = "Branches"

    BranchId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    BranchKey = Column(TSQLUnicode(50), unique=True, nullable=False)
    Name = Column(TSQLUnicode(150), unique=True, nullable=False)
    DegreeLevel = Column(TSQLUnicode(50), nullable=False)
    SortOrder = Column(Integer, nullable=False, default=0)

    programs = relationship("Program", back_populates="branch")


class Program(Base):
    """A specialization within a branch, e.g. 'B.Tech - Artificial Intelligence & Machine Learning'.

    Seeded from ``app/data/programs.json``. Users, clubs, and proposals all point here.
    """

    __tablename__ = "Programs"

    ProgramId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    ProgramKey = Column(TSQLUnicode(100), unique=True, nullable=False)
    BranchId = Column(Integer, ForeignKey("Branches.BranchId"), nullable=False, index=True)
    Name = Column(TSQLUnicode(150), nullable=False)
    FullName = Column(TSQLUnicode(255), nullable=False)
    CollaborationPartner = Column(TSQLUnicode(150), nullable=True)
    SortOrder = Column(Integer, nullable=False, default=0)

    branch = relationship("Branch", back_populates="programs", lazy="joined")
    users = relationship("User", back_populates="program")
    clubs = relationship("Club", back_populates="program")
    proposals = relationship("ClubProposal", back_populates="program")


class Role(Base):
    __tablename__ = "Roles"

    RoleId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    RoleName = Column(TSQLUnicode(30), unique=True, nullable=False)

    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "Users"

    UserId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    Email = Column(TSQLUnicode(256), unique=True, nullable=False, index=True)
    PasswordHash = Column(TSQLUnicode(256), nullable=False)
    FullName = Column(TSQLUnicode(150), nullable=False)
    RoleId = Column(Integer, ForeignKey("Roles.RoleId"), nullable=False)
    ProgramId = Column(Integer, ForeignKey("Programs.ProgramId"), nullable=True)
    IsActive = Column(Boolean, nullable=False, default=True)
    TokenVersion = Column(Integer, nullable=False, default=1)
    CreatedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    role = relationship("Role", back_populates="users", lazy="joined")
    program = relationship("Program", back_populates="users", lazy="joined")
    managed_clubs = relationship("Club", back_populates="manager")
    memberships = relationship("ClubMembership", back_populates="user")
    registrations = relationship("EventRegistration", back_populates="user")
    attendances = relationship("Attendance", foreign_keys="Attendance.UserId", back_populates="user")
    proposals = relationship("ClubProposal", back_populates="applicant")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Club(Base):
    __tablename__ = "Clubs"

    ClubId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    Name = Column(TSQLUnicode(150), unique=True, nullable=False, index=True)
    ProgramId = Column(Integer, ForeignKey("Programs.ProgramId"), nullable=False)
    ManagerUserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    Description = Column(TSQLText, nullable=True)
    Motives = Column(TSQLText, nullable=True)
    PastAchievements = Column(TSQLJson, nullable=True, default=list)
    LeadershipContacts = Column(TSQLJson, nullable=True, default=list)
    LogoUrl = Column(TSQLUnicode(500), nullable=True)
    CharterPdfUrl = Column(TSQLUnicode(500), nullable=True)
    Status = Column(TSQLUnicode(20), nullable=False, default="pending")
    CreatedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    __table_args__ = (
        CheckConstraint('"Status" IN (\'pending\', \'active\', \'suspended\')', name="CK_Clubs_Status"),
    )

    program = relationship("Program", back_populates="clubs", lazy="joined")
    manager = relationship("User", back_populates="managed_clubs", lazy="joined")
    members = relationship("ClubMembership", back_populates="club", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="club", cascade="all, delete-orphan")


class ClubMembership(Base):
    __tablename__ = "ClubMemberships"

    MembershipId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    ClubId = Column(Integer, ForeignKey("Clubs.ClubId", ondelete="CASCADE"), nullable=False)
    UserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    Status = Column(TSQLUnicode(20), nullable=False, default="requested")
    Role = Column(TSQLUnicode(30), nullable=False, default="Member")
    JoinedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    __table_args__ = (
        UniqueConstraint("ClubId", "UserId", name="UQ_Club_User"),
        CheckConstraint('"Status" IN (\'requested\', \'active\', \'removed\')', name="CK_ClubMemberships_Status"),
    )

    club = relationship("Club", back_populates="members")
    user = relationship("User", back_populates="memberships", lazy="joined")


class Event(Base):
    __tablename__ = "Events"

    EventId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    ClubId = Column(Integer, ForeignKey("Clubs.ClubId", ondelete="CASCADE"), nullable=False)
    Title = Column(TSQLUnicode(200), nullable=False)
    VenueText = Column(TSQLUnicode(200), nullable=True)
    PosterUrl = Column(TSQLUnicode(500), nullable=True)
    EventDate = Column(TSQLDateTime, nullable=False)
    RegistrationDeadline = Column(TSQLDateTime, nullable=False)
    Capacity = Column(Integer, nullable=False)
    Status = Column(TSQLUnicode(20), nullable=False, default="draft")
    CreatedByUserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)

    __table_args__ = (
        CheckConstraint('"Capacity" > 0', name="CK_Events_Capacity"),
        CheckConstraint('"Status" IN (\'draft\', \'published\', \'completed\', \'cancelled\')', name="CK_Events_Status"),
        CheckConstraint('"RegistrationDeadline" <= "EventDate"', name="CK_Deadline_Before_Event"),
        Index("IX_Events_ClubId_Date", "ClubId", "EventDate"),
    )

    club = relationship("Club", back_populates="events", lazy="joined")
    creator = relationship("User", foreign_keys=[CreatedByUserId])
    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="event", cascade="all, delete-orphan")
    outcome = relationship("EventOutcome", back_populates="event", uselist=False, cascade="all, delete-orphan")


class EventRegistration(Base):
    __tablename__ = "EventRegistrations"

    RegistrationId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    EventId = Column(Integer, ForeignKey("Events.EventId", ondelete="CASCADE"), nullable=False)
    UserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    Status = Column(TSQLUnicode(20), nullable=False, default="confirmed")
    RegisteredAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    __table_args__ = (
        UniqueConstraint("EventId", "UserId", name="UQ_Event_User_Reg"),
        CheckConstraint('"Status" IN (\'confirmed\', \'waitlisted\', \'cancelled\')', name="CK_EventRegistrations_Status"),
        Index("IX_Reg_EventId_Status", "EventId", "Status"),
    )

    event = relationship("Event", back_populates="registrations")
    user = relationship("User", back_populates="registrations", lazy="joined")


class Attendance(Base):
    __tablename__ = "Attendance"

    AttendanceId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    EventId = Column(Integer, ForeignKey("Events.EventId", ondelete="CASCADE"), nullable=False)
    UserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    CheckedInAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())
    RecordedByUserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)

    __table_args__ = (
        UniqueConstraint("EventId", "UserId", name="UQ_Event_User_Att"),
    )

    event = relationship("Event", back_populates="attendances")
    user = relationship("User", foreign_keys=[UserId], back_populates="attendances", lazy="joined")
    recorded_by = relationship("User", foreign_keys=[RecordedByUserId])


class ClubProposal(Base):
    __tablename__ = "ClubProposals"

    ProposalId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    ApplicantUserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    ProposedName = Column(TSQLUnicode(150), nullable=False)
    ProgramId = Column(Integer, ForeignKey("Programs.ProgramId"), nullable=False)
    Description = Column(TSQLText, nullable=False)
    Status = Column(TSQLUnicode(20), nullable=False, default="submitted")
    SubmittedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    __table_args__ = (
        CheckConstraint('"Status" IN (\'submitted\', \'changes_requested\', \'approved\', \'rejected\')', name="CK_ClubProposals_Status"),
    )

    applicant = relationship("User", back_populates="proposals", lazy="joined")
    program = relationship("Program", back_populates="proposals", lazy="joined")
    approvals = relationship("Approval", back_populates="proposal", cascade="all, delete-orphan", order_by="Approval.DecidedAt")


class Approval(Base):
    __tablename__ = "Approvals"

    ApprovalId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    ProposalId = Column(Integer, ForeignKey("ClubProposals.ProposalId", ondelete="CASCADE"), nullable=False)
    ReviewerUserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    Stage = Column(TSQLUnicode(20), nullable=False)
    Decision = Column(TSQLUnicode(20), nullable=False)
    Comment = Column(TSQLText, nullable=True)
    DecidedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    __table_args__ = (
        CheckConstraint('"Stage" IN (\'faculty\', \'hod\')', name="CK_Approvals_Stage"),
        CheckConstraint('"Decision" IN (\'approve\', \'reject\', \'changes_requested\')', name="CK_Approvals_Decision"),
    )

    proposal = relationship("ClubProposal", back_populates="approvals")
    reviewer = relationship("User", lazy="joined")


class EventOutcome(Base):
    __tablename__ = "EventOutcomes"

    OutcomeId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    EventId = Column(Integer, ForeignKey("Events.EventId", ondelete="CASCADE"), unique=True, nullable=False)
    Summary = Column(TSQLText, nullable=True)
    AttendanceCountSnapshot = Column(Integer, nullable=False, default=0)
    SubmittedByUserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    SubmittedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    event = relationship("Event", back_populates="outcome")
    submitted_by = relationship("User")


class Notification(Base):
    __tablename__ = "Notifications"

    NotificationId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    UserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    Type = Column(TSQLUnicode(50), nullable=False)
    Message = Column(TSQLUnicode(500), nullable=False)
    IsRead = Column(Boolean, nullable=False, default=False)
    CreatedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    __table_args__ = (
        Index("IX_Notif_UserId_IsRead", "UserId", "IsRead"),
    )

    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "AuditLogs"

    AuditLogId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    ActorUserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    Action = Column(TSQLUnicode(100), nullable=False)
    EntityType = Column(TSQLUnicode(50), nullable=False)
    EntityId = Column(Integer, nullable=False)
    Details = Column(TSQLText, nullable=True)
    CreatedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    __table_args__ = (
        Index("IX_Audit_Entity", "EntityType", "EntityId"),
    )

    actor = relationship("User", lazy="joined")


class RefreshSession(Base):
    """Server-side refresh-token session with rotation/reuse detection.

    Only a SHA-256 digest of the opaque refresh token is stored. Revoking the
    row (or the whole family) invalidates the corresponding refresh token.
    """

    __tablename__ = "RefreshSessions"

    SessionId = Column(TSQLUnicode(64), primary_key=True, index=True)
    UserId = Column(
        Integer,
        ForeignKey("Users.UserId", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    FamilyId = Column(TSQLUnicode(64), nullable=False, index=True)
    TokenHash = Column(TSQLUnicode(64), unique=True, nullable=False, index=True)
    IssuedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())
    ExpiresAt = Column(TSQLDateTime, nullable=False)
    RevokedAt = Column(TSQLDateTime, nullable=True)
    ReplacedBySessionId = Column(TSQLUnicode(64), nullable=True)
    ReplacedAt = Column(TSQLDateTime, nullable=True)
    IpAddress = Column(TSQLUnicode(45), nullable=True)
    UserAgent = Column(TSQLUnicode(255), nullable=True)

    __table_args__ = (
        Index("IX_RefreshSessions_UserId_FamilyId", "UserId", "FamilyId"),
        Index("IX_RefreshSessions_ExpiresAt", "ExpiresAt"),
    )

    user = relationship("User")


class AuthThrottle(Base):
    """Persistent brute-force / abuse counters for authentication endpoints."""

    __tablename__ = "AuthThrottle"

    ThrottleId = Column(Integer, Identity(start=1, increment=1), primary_key=True, index=True)
    Scope = Column(TSQLUnicode(32), nullable=False)
    KeyHash = Column(TSQLUnicode(64), nullable=False)
    FailureCount = Column(Integer, nullable=False, default=0)
    WindowStartedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())
    BlockedUntil = Column(TSQLDateTime, nullable=True)
    UpdatedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    __table_args__ = (
        UniqueConstraint("Scope", "KeyHash", name="UQ_AuthThrottle_Scope_Key"),
        Index("IX_AuthThrottle_BlockedUntil", "BlockedUntil"),
    )


class UploadedFile(Base):
    __tablename__ = "UploadedFiles"

    FileId = Column(TSQLUnicode(64), primary_key=True, index=True)
    OwnerUserId = Column(Integer, ForeignKey("Users.UserId"), nullable=False)
    EntityType = Column(TSQLUnicode(50), nullable=False)
    EntityId = Column(Integer, nullable=False)
    OriginalFilename = Column(TSQLUnicode(255), nullable=False)
    BlobPath = Column(TSQLUnicode(500), nullable=False)
    MimeType = Column(TSQLUnicode(100), nullable=False)
    FileSizeBytes = Column(Integer, nullable=False)
    CreatedAt = Column(TSQLDateTime, nullable=False, default=utc_now, server_default=utcnow_sql())

    owner = relationship("User")
