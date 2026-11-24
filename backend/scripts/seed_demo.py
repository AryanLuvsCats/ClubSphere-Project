"""Seed the development database with realistic demo data.

Creates one account per role (password: ``password123``), clubs spread across
different programs, events with registrations and attendance, and club
proposals covering every workflow state.

Run from the ``backend/`` directory::

    python scripts/seed_demo.py

Safe to re-run: it exits early if demo users already exist.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

# Make the backend package importable when run as a plain script.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.database import Base, engine, SessionLocal  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.core.academic_seed import seed_academic_data  # noqa: E402
from app.models.models import (  # noqa: E402
    Role,
    RoleNameEnum,
    Program,
    User,
    Club,
    ClubMembership,
    Event,
    EventRegistration,
    Attendance,
    ClubProposal,
    Approval,
    AuditLog,
    Notification,
)

DEMO_PASSWORD = "password123"


def utc_naive(days_offset: int = 0, hours_offset: int = 0) -> datetime:
    """A naive UTC timestamp offset from now (SQLite stores naive datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        days=days_offset, hours=hours_offset
    )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # ---- Baseline: roles + academic data from JSON ----------------------
        for role_name in [r.value for r in RoleNameEnum]:
            if not db.query(Role).filter(Role.RoleName == role_name).first():
                db.add(Role(RoleName=role_name))
        db.commit()
        academic = seed_academic_data(db)

        if db.query(User).filter(User.Email == "admin@clubsphere.edu").first():
            print("Demo data already present — nothing to do.")
            return

        def prog(key: str) -> Program:
            p = db.query(Program).filter(Program.ProgramKey == key).first()
            if p is None:
                raise SystemExit(f"Program key '{key}' not found — is the JSON data seeded?")
            return p

        # ---- Users: one account per role + extra students -------------------
        def make_user(email: str, name: str, role_name: str, program_key: str | None) -> User:
            role = db.query(Role).filter(Role.RoleName == role_name).first()
            user = User(
                Email=email,
                PasswordHash=get_password_hash(DEMO_PASSWORD),
                FullName=name,
                RoleId=role.RoleId,
                ProgramId=prog(program_key).ProgramId if program_key else None,
                IsActive=True,
            )
            db.add(user)
            db.flush()
            return user

        admin = make_user("admin@clubsphere.edu", "Aditi Verma", RoleNameEnum.ADMINISTRATOR.value, "mba_strategic_hr")
        hod = make_user("hod@clubsphere.edu", "Dr. Rajesh Kumar", RoleNameEnum.HOD.value, "btech_cse")
        faculty = make_user("faculty@clubsphere.edu", "Dr. Neha Sharma", RoleNameEnum.FACULTY.value, "btech_cse")
        manager = make_user("manager@clubsphere.edu", "Vikram Desai", RoleNameEnum.CLUB_MANAGER.value, "btech_robotics")

        students = [
            make_user("student@clubsphere.edu", "Aryan Chatterjee", RoleNameEnum.STUDENT.value, "btech_cse_aiml"),
            make_user("student2@clubsphere.edu", "Priya Patel", RoleNameEnum.STUDENT.value, "bca_hons"),
            make_user("student3@clubsphere.edu", "Rohan Gupta", RoleNameEnum.STUDENT.value, "mba_ds_ai"),
            make_user("student4@clubsphere.edu", "Sneha Iyer", RoleNameEnum.STUDENT.value, "bdes_fashion"),
            make_user("student5@clubsphere.edu", "Kabir Singh", RoleNameEnum.STUDENT.value, "btech_robotics"),
            make_user("student6@clubsphere.edu", "Ananya Roy", RoleNameEnum.STUDENT.value, "bajmc_general"),
            make_user("student7@clubsphere.edu", "Vikram Nair", RoleNameEnum.STUDENT.value, "bcom_hons"),
            make_user("student8@clubsphere.edu", "Meera Krishnan", RoleNameEnum.STUDENT.value, "btech_cse"),
            make_user("student9@clubsphere.edu", "Arjun Mehta", RoleNameEnum.STUDENT.value, "mtech_cse_aiml"),
            make_user("student10@clubsphere.edu", "Zara Khan", RoleNameEnum.STUDENT.value, "ba_psychology"),
        ]
        db.commit()

        # ---- Clubs across different programs (7 Core University Clubs) -------
        def make_club(name: str, program_key: str, mgr: User, description: str) -> Club:
            club = db.query(Club).filter(Club.Name == name).first()
            if club:
                club.ProgramId = prog(program_key).ProgramId
                club.ManagerUserId = mgr.UserId
                club.Description = description
                club.Status = "active"
            else:
                club = Club(
                    Name=name,
                    ProgramId=prog(program_key).ProgramId,
                    ManagerUserId=mgr.UserId,
                    Description=description,
                    Status="active",
                )
                db.add(club)
            db.flush()
            # The manager is an active Lead member of every club they run.
            lead_mem = db.query(ClubMembership).filter(
                ClubMembership.ClubId == club.ClubId,
                ClubMembership.UserId == mgr.UserId,
            ).first()
            if not lead_mem:
                db.add(ClubMembership(ClubId=club.ClubId, UserId=mgr.UserId, Status="active", Role="Lead"))
            else:
                lead_mem.Status = "active"
                lead_mem.Role = "Lead"
            db.flush()
            return club

        s = students
        aiml = make_club(
            "AIML Club", "btech_cse_aiml", faculty,
            "Pioneering Artificial Intelligence, Machine Learning, deep learning workshops, and data science hackathons.",
        )
        robox = make_club(
            "RoboX", "btech_robotics", manager,
            "Hardware prototyping, autonomous robotics, IoT, ROS2 builds, and inter-college bot competitions.",
        )
        finearts = make_club(
            "FineArts", "ba_liberal_arts", manager,
            "Painting, sketching, digital illustration masterclasses, campus wall murals, and annual art exhibitions.",
        )
        moot = make_club(
            "Moot Court", "ballb_integrated", faculty,
            "Mock trial competitions, constitutional law debates, appellate legal drafting, and public speaking.",
        )
        codex = make_club(
            "Codex", "btech_cse", manager,
            "Competitive programming, open-source engineering, full-stack software development, and coding bootcamps.",
        )
        literary = make_club(
            "Literary", "bajmc_general", manager,
            "Creative writing, poetry slams, book clubs, campus newsletters, and editorial publishing.",
        )
        bioverse = make_club(
            "Bioverse", "btech_biotech", faculty,
            "Biotechnology research, bioinformatics algorithms, environmental sustainability projects, and bio-seminars.",
        )
        db.commit()

        def add_members(club: Club, users: list[User]) -> None:
            for u in users:
                existing_mem = db.query(ClubMembership).filter(
                    ClubMembership.ClubId == club.ClubId,
                    ClubMembership.UserId == u.UserId,
                ).first()
                if not existing_mem:
                    db.add(ClubMembership(ClubId=club.ClubId, UserId=u.UserId, Status="active", Role="Member"))
            db.flush()

        add_members(aiml, [s[0], s[2], s[7], s[8], s[9]])
        add_members(robox, [s[0], s[4], s[7], s[8]])
        add_members(finearts, [s[3], s[9], s[2]])
        add_members(moot, [s[1], s[6], s[7]])
        add_members(codex, [s[0], s[1], s[6], s[7], s[8]])
        add_members(literary, [s[5], s[9], s[3]])
        add_members(bioverse, [s[0], s[4], s[8]])
        db.commit()

        # ---- Events with registrations & attendance -------------------------
        def make_event(
            club: Club,
            title: str,
            venue: str,
            days_offset: int,
            capacity: int,
            status: str,
            creator: User,
        ) -> Event:
            event = db.query(Event).filter(Event.ClubId == club.ClubId, Event.Title == title).first()
            if event:
                event.VenueText = venue
                event.EventDate = utc_naive(days_offset=days_offset, hours_offset=10)
                event.RegistrationDeadline = utc_naive(days_offset=days_offset - 3)
                event.Capacity = capacity
                event.Status = status
                event.CreatedByUserId = creator.UserId
            else:
                event = Event(
                    ClubId=club.ClubId,
                    Title=title,
                    VenueText=venue,
                    EventDate=utc_naive(days_offset=days_offset, hours_offset=10),
                    RegistrationDeadline=utc_naive(days_offset=days_offset - 3),
                    Capacity=capacity,
                    Status=status,
                    CreatedByUserId=creator.UserId,
                )
                db.add(event)
            db.flush()
            return event

        def register(event: Event, users: list[User], attended: int = 0) -> None:
            for i, u in enumerate(users):
                if not db.query(EventRegistration).filter(
                    EventRegistration.EventId == event.EventId,
                    EventRegistration.UserId == u.UserId,
                ).first():
                    db.add(EventRegistration(EventId=event.EventId, UserId=u.UserId, Status="confirmed"))
                if i < attended:
                    if not db.query(Attendance).filter(
                        Attendance.EventId == event.EventId,
                        Attendance.UserId == u.UserId,
                    ).first():
                        db.add(
                            Attendance(
                                EventId=event.EventId,
                                UserId=u.UserId,
                                CheckedInAt=utc_naive(days_offset=0),
                                RecordedByUserId=manager.UserId,
                            )
                        )
            db.flush()

        bootcamp = make_event(robox, "Autonomous Robotics Bootcamp 2026", "Innovation Workshop, Block C", 14, 40, "published", manager)
        register(bootcamp, [s[0], s[4], s[7], s[8]])

        hackathon = make_event(codex, "Inter-College CodeSprint Hackathon", "Central Computing Lab", 21, 60, "published", manager)
        register(hackathon, [s[0], s[1], s[6], s[7], s[8]])

        meetup = make_event(aiml, "AI Paper Reading Meetup & Kaggle Sprint", "Seminar Hall 2", -10, 30, "completed", faculty)
        register(meetup, [s[0], s[2], s[7], s[8], s[9]], attended=4)

        arts_jam = make_event(finearts, "Annual Wall Mural Jam", "Design Studio, Block A", 10, 25, "published", manager)
        register(arts_jam, [s[3], s[9], s[2]])

        moot_comp = make_event(moot, "National Moot Court Colloquium", "Moot Court Hall", -25, 50, "completed", faculty)
        register(moot_comp, [s[1], s[6], s[7]], attended=3)

        make_event(literary, "Campus Poetry Slam & Open Mic", "Main Quadrangle", 30, 20, "draft", manager)
        make_event(bioverse, "Bio-Innovation & Bioinformatics Seminar", "Bio-Eng Lab 108", 18, 45, "published", faculty)
        db.commit()

        # ---- Proposals covering every workflow state ------------------------
        def make_proposal(applicant: User, name: str, program_key: str, description: str, status: str) -> ClubProposal:
            prop = ClubProposal(
                ApplicantUserId=applicant.UserId,
                ProposedName=name,
                ProgramId=prog(program_key).ProgramId,
                Description=description,
                Status=status,
                SubmittedAt=utc_naive(days_offset=-5),
            )
            db.add(prop)
            db.flush()
            return prop

        def add_audit(actor: User, action: str, entity_id: int, details: str) -> None:
            db.add(
                AuditLog(
                    ActorUserId=actor.UserId,
                    Action=action,
                    EntityType="ClubProposals",
                    EntityId=entity_id,
                    Details=details,
                    CreatedAt=utc_naive(days_offset=-4),
                )
            )

        # 1. Pending — awaiting first faculty review.
        p1 = make_proposal(
            s[9], "Rocketry & Astronomy Society", "btech_electrical",
            "Model rocketry launches, telescope nights and introductory astrodynamics workshops for all majors.",
            "submitted",
        )
        add_audit(s[9], "PROPOSAL_SUBMITTED", p1.ProposalId, f"Proposal '{p1.ProposedName}' submitted for review.")

        # 2. Changes requested by faculty.
        p2 = make_proposal(
            s[3], "Drama & Theatre Society", "ba_liberal_arts",
            "A student-run repertory staging two productions a year with open auditions across every program.",
            "changes_requested",
        )
        db.add(Approval(
            ProposalId=p2.ProposalId, ReviewerUserId=faculty.UserId, Stage="faculty",
            Decision="changes_requested",
            Comment="Please add a semester-wise activity plan and a tentative budget before we can recommend this.",
            DecidedAt=utc_naive(days_offset=-4),
        ))
        add_audit(faculty, "PROPOSAL_REVIEWED", p2.ProposalId, "Faculty requested changes on proposal.")

        # 3. Approved — auto-created club, applicant assigned as Lead.
        p3 = make_proposal(
            s[7], "Fintech Analytics Cell", "mba_business_analytics",
            "Applied analytics cell building credit-risk and fraud-detection models with live market datasets.",
            "approved",
        )
        db.add(Approval(
            ProposalId=p3.ProposalId, ReviewerUserId=faculty.UserId, Stage="faculty",
            Decision="approve", Comment="Strong industry-relevant scope. Recommended for chartership.",
            DecidedAt=utc_naive(days_offset=-4, hours_offset=2),
        ))
        db.add(Approval(
            ProposalId=p3.ProposalId, ReviewerUserId=hod.UserId, Stage="hod",
            Decision="approve", Comment="Approved. Welcome to ClubSphere!",
            DecidedAt=utc_naive(days_offset=-4, hours_offset=5),
        ))
        fintech_cell = make_club(
            "Fintech Analytics Cell", "mba_business_analytics", s[7],
            "Applied analytics cell building credit-risk and fraud-detection models with live market datasets.",
        )
        add_members(fintech_cell, [s[2], s[6]])
        add_audit(faculty, "PROPOSAL_REVIEWED", p3.ProposalId, "Faculty recommended proposal.")
        add_audit(hod, "PROPOSAL_APPROVED", p3.ProposalId, "HOD approved proposal; club chartered.")

        # 4. Rejected.
        p4 = make_proposal(
            s[4], "Esports Arena", "bca_hons",
            "Competitive gaming tournaments across Valorant, CS2 and FIFA with a campus bootcamp.",
            "rejected",
        )
        db.add(Approval(
            ProposalId=p4.ProposalId, ReviewerUserId=faculty.UserId, Stage="faculty",
            Decision="reject",
            Comment="The university does not currently charter gaming organisations. Consider a Game Development Club instead.",
            DecidedAt=utc_naive(days_offset=-3),
        ))
        add_audit(faculty, "PROPOSAL_REVIEWED", p4.ProposalId, "Faculty rejected proposal.")
        db.commit()

        # ---- A couple of notifications so the bell isn't empty ---------------
        db.add(Notification(
            UserId=s[7].UserId, Type="PROPOSAL_APPROVED",
            Message="Your proposal 'Fintech Analytics Cell' was approved — the club is now live!",
            IsRead=False, CreatedAt=utc_naive(days_offset=-4),
        ))
        db.add(Notification(
            UserId=manager.UserId, Type="EVENT_REMINDER",
            Message="Robotics Bootcamp 2026 starts in two weeks. Registration is open.",
            IsRead=False, CreatedAt=utc_naive(days_offset=-1),
        ))
        db.commit()

        print("Demo data seeded successfully.")
        print(f"  Academic: {academic['branches']} branches, {academic['programs']} programs.")
        print(f"  Users:    4 staff + 1 student account per demo student (10 students).")
        print(f"  Clubs:    7 active clubs across 7 programs.")
        print(f"  Events:   6 events (2 completed, 3 published, 1 draft).")
        print(f"  Proposals: 4 (submitted / changes_requested / approved / rejected).")
        print(f"\nAll demo accounts share the password: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
