"""Database seed script for university clubs in ClubSphere.

Populates realistic seed data for the 7 core university clubs:
1. AIML Club (Category: Technology / AI)
2. RoboX (Category: Engineering / Robotics)
3. FineArts (Category: Arts & Culture)
4. Moot Court (Category: Law / Debate)
5. Codex (Category: Technology / Programming)
6. Literary (Category: Literature & Media)
7. Bioverse (Category: Science / Biotech)

Idempotent: Uses upsert logic and checks for existing records before inserting.
Safe to execute multiple times against development, staging, or production databases.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

# Ensure the backend directory is in the Python import path
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
)

DEFAULT_PASSWORD = "password123"


def utc_naive(days_offset: int = 0, hours_offset: int = 0) -> datetime:
    """Return a naive UTC timestamp offset from now."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        days=days_offset, hours=hours_offset
    )


def get_or_create_user(
    db,
    email: str,
    full_name: str,
    role_name: str,
    program_key: str | None = None,
) -> User:
    """Find existing user by email or create a new user."""
    user = db.query(User).filter(User.Email == email.lower()).first()
    role = db.query(Role).filter(Role.RoleName == role_name).first()
    if not role:
        role = Role(RoleName=role_name)
        db.add(role)
        db.flush()

    program_id = None
    if program_key:
        prog = db.query(Program).filter(Program.ProgramKey == program_key).first()
        if prog:
            program_id = prog.ProgramId

    if user:
        # Update user attributes if needed
        user.FullName = full_name
        user.RoleId = role.RoleId
        if program_id and not user.ProgramId:
            user.ProgramId = program_id
        db.flush()
        return user

    user = User(
        Email=email.lower(),
        PasswordHash=get_password_hash(DEFAULT_PASSWORD),
        FullName=full_name,
        RoleId=role.RoleId,
        ProgramId=program_id,
        IsActive=True,
    )
    db.add(user)
    db.flush()
    return user


def upsert_club(
    db,
    name: str,
    program_key: str,
    manager: User,
    description: str,
    status: str = "active",
) -> Club:
    """Find existing club by name or create a new one, ensuring idempotent execution."""
    prog = db.query(Program).filter(Program.ProgramKey == program_key).first()
    if not prog:
        raise ValueError(f"Program with key '{program_key}' not found in database.")

    club = db.query(Club).filter(Club.Name == name).first()
    if club:
        club.ProgramId = prog.ProgramId
        club.ManagerUserId = manager.UserId
        club.Description = description
        club.Status = status
        db.flush()
    else:
        club = Club(
            Name=name,
            ProgramId=prog.ProgramId,
            ManagerUserId=manager.UserId,
            Description=description,
            Status=status,
            CreatedAt=utc_naive(days_offset=-30),
        )
        db.add(club)
        db.flush()

    # Ensure manager has an active Lead membership in the club
    lead_membership = (
        db.query(ClubMembership)
        .filter(
            ClubMembership.ClubId == club.ClubId,
            ClubMembership.UserId == manager.UserId,
        )
        .first()
    )
    if lead_membership:
        lead_membership.Role = "Lead"
        lead_membership.Status = "active"
    else:
        db.add(
            ClubMembership(
                ClubId=club.ClubId,
                UserId=manager.UserId,
                Status="active",
                Role="Lead",
                JoinedAt=utc_naive(days_offset=-30),
            )
        )
    db.flush()
    return club


def add_member_if_missing(db, club: Club, user: User, role: str = "Member") -> None:
    """Add a user to a club membership if not already present."""
    existing = (
        db.query(ClubMembership)
        .filter(
            ClubMembership.ClubId == club.ClubId,
            ClubMembership.UserId == user.UserId,
        )
        .first()
    )
    if not existing:
        db.add(
            ClubMembership(
                ClubId=club.ClubId,
                UserId=user.UserId,
                Status="active",
                Role=role,
                JoinedAt=utc_naive(days_offset=-15),
            )
        )
        db.flush()


def upsert_event(
    db,
    club: Club,
    title: str,
    venue: str,
    days_offset: int,
    capacity: int,
    status: str,
    creator: User,
) -> Event:
    """Upsert an event for a club by matching club ID and title."""
    event = (
        db.query(Event)
        .filter(Event.ClubId == club.ClubId, Event.Title == title)
        .first()
    )
    event_date = utc_naive(days_offset=days_offset, hours_offset=10)
    deadline = utc_naive(days_offset=days_offset - 3, hours_offset=18)

    if event:
        event.VenueText = venue
        event.EventDate = event_date
        event.RegistrationDeadline = deadline
        event.Capacity = capacity
        event.Status = status
        event.CreatedByUserId = creator.UserId
        db.flush()
        return event

    event = Event(
        ClubId=club.ClubId,
        Title=title,
        VenueText=venue,
        EventDate=event_date,
        RegistrationDeadline=deadline,
        Capacity=capacity,
        Status=status,
        CreatedByUserId=creator.UserId,
    )
    db.add(event)
    db.flush()
    return event


def register_users_for_event(db, event: Event, users: list[User], attended_count: int = 0) -> None:
    """Register users for an event idempotently, with optional attendance records."""
    for i, u in enumerate(users):
        reg = (
            db.query(EventRegistration)
            .filter(
                EventRegistration.EventId == event.EventId,
                EventRegistration.UserId == u.UserId,
            )
            .first()
        )
        if not reg:
            db.add(
                EventRegistration(
                    EventId=event.EventId,
                    UserId=u.UserId,
                    Status="confirmed",
                    RegisteredAt=utc_naive(days_offset=-4),
                )
            )
            db.flush()

        if i < attended_count:
            att = (
                db.query(Attendance)
                .filter(
                    Attendance.EventId == event.EventId,
                    Attendance.UserId == u.UserId,
                )
                .first()
            )
            if not att:
                db.add(
                    Attendance(
                        EventId=event.EventId,
                        UserId=u.UserId,
                        CheckedInAt=event.EventDate,
                        RecordedByUserId=event.CreatedByUserId,
                    )
                )
                db.flush()


def seed_clubs() -> None:
    """Main execution entry point to seed the 7 university clubs."""
    print("==> Initializing ClubSphere database schema and baseline data...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Ensure baseline roles exist
        for role_name in [r.value for r in RoleNameEnum]:
            if not db.query(Role).filter(Role.RoleName == role_name).first():
                db.add(Role(RoleName=role_name))
        db.commit()

        # 2. Ensure academic structure (branches + programs) is seeded from JSON
        academic = seed_academic_data(db)
        print(f"==> Academic structure: {academic['branches']} branches, {academic['programs']} programs verified.")

        # 3. Create dummy student pool for realistic club memberships
        print("==> Provisioning student and manager user accounts...")
        students = [
            get_or_create_user(db, "aarav.sharma@clubsphere.edu", "Aarav Sharma", RoleNameEnum.STUDENT.value, "btech_cse_aiml"),
            get_or_create_user(db, "ananya.iyer@clubsphere.edu", "Ananya Iyer", RoleNameEnum.STUDENT.value, "btech_robotics"),
            get_or_create_user(db, "dev.patel@clubsphere.edu", "Dev Patel", RoleNameEnum.STUDENT.value, "ba_liberal_arts"),
            get_or_create_user(db, "ishita.gupta@clubsphere.edu", "Ishita Gupta", RoleNameEnum.STUDENT.value, "ballb_integrated"),
            get_or_create_user(db, "kabir.mehta@clubsphere.edu", "Kabir Mehta", RoleNameEnum.STUDENT.value, "btech_cse"),
            get_or_create_user(db, "meera.nair@clubsphere.edu", "Meera Nair", RoleNameEnum.STUDENT.value, "bajmc_general"),
            get_or_create_user(db, "rohan.deshmukh@clubsphere.edu", "Rohan Deshmukh", RoleNameEnum.STUDENT.value, "btech_biotech"),
            get_or_create_user(db, "sneha.verma@clubsphere.edu", "Sneha Verma", RoleNameEnum.STUDENT.value, "btech_cse_aiml"),
            get_or_create_user(db, "tanmay.bhatia@clubsphere.edu", "Tanmay Bhatia", RoleNameEnum.STUDENT.value, "btech_robotics"),
            get_or_create_user(db, "zara.khan@clubsphere.edu", "Zara Khan", RoleNameEnum.STUDENT.value, "ba_liberal_arts"),
            get_or_create_user(db, "ritik.choudhary@clubsphere.edu", "Ritik Choudhary", RoleNameEnum.STUDENT.value, "ballb_integrated"),
            get_or_create_user(db, "priya.singh@clubsphere.edu", "Priya Singh", RoleNameEnum.STUDENT.value, "btech_cse"),
            get_or_create_user(db, "aditya.joshi@clubsphere.edu", "Aditya Joshi", RoleNameEnum.STUDENT.value, "bajmc_general"),
            get_or_create_user(db, "diya.sen@clubsphere.edu", "Diya Sen", RoleNameEnum.STUDENT.value, "btech_biotech"),
            get_or_create_user(db, "arjun.kapoor@clubsphere.edu", "Arjun Kapoor", RoleNameEnum.STUDENT.value, "btech_cse"),
        ]

        # 4. Create dedicated managers for each club
        mgr_aiml = get_or_create_user(db, "lead.aiml@clubsphere.edu", "Dr. Aakash Kulkarni", RoleNameEnum.CLUB_MANAGER.value, "btech_cse_aiml")
        mgr_robox = get_or_create_user(db, "lead.robox@clubsphere.edu", "Vikramaditya Rao", RoleNameEnum.CLUB_MANAGER.value, "btech_robotics")
        mgr_finearts = get_or_create_user(db, "lead.finearts@clubsphere.edu", "Sunaina Kashyap", RoleNameEnum.CLUB_MANAGER.value, "ba_liberal_arts")
        mgr_moot = get_or_create_user(db, "lead.mootcourt@clubsphere.edu", "Adv. Siddharth Sen", RoleNameEnum.CLUB_MANAGER.value, "ballb_integrated")
        mgr_codex = get_or_create_user(db, "lead.codex@clubsphere.edu", "Karthik Sundaram", RoleNameEnum.CLUB_MANAGER.value, "btech_cse")
        mgr_literary = get_or_create_user(db, "lead.literary@clubsphere.edu", "Nandini Mukherjee", RoleNameEnum.CLUB_MANAGER.value, "bajmc_general")
        mgr_bioverse = get_or_create_user(db, "lead.bioverse@clubsphere.edu", "Dr. Shalini Menon", RoleNameEnum.CLUB_MANAGER.value, "btech_biotech")
        db.commit()

        # 5. Define rich metadata for the 7 university clubs
        clubs_spec = [
            {
                "name": "AIML Club",
                "category": "Technology / AI",
                "program_key": "btech_cse_aiml",
                "manager": mgr_aiml,
                "description": (
                    "**Pioneering Artificial Intelligence, Machine Learning & Intelligent Systems**\n\n"
                    "• **Category:** Technology / AI\n"
                    "• **Focus:** Artificial Intelligence, Machine Learning, deep learning workshops, and data science hackathons.\n"
                    "• **Meeting Schedule:** Every Wednesday at 5:00 PM | Turing AI Research Lab (Block B, Room 204)\n"
                    "• **Contact Email:** aiml.club@clubsphere.edu\n"
                    "• **Key Initiatives:** Weekly research paper reviews, Kaggle sprint competitions, PyTorch/TensorFlow bootcamps, and foundational Generative AI workshops."
                ),
                "members": [students[0], students[7], students[4], students[11], students[14]],
                "events": [
                    {
                        "title": "Deep Learning & Transformer Architectures Workshop",
                        "venue": "Turing Lab (Block B, Room 204)",
                        "days_offset": 12,
                        "capacity": 60,
                        "status": "published",
                    },
                    {
                        "title": "Campus Data Science Hackathon 2026",
                        "venue": "Main Auditorium & Computing Center",
                        "days_offset": -18,
                        "capacity": 100,
                        "status": "completed",
                        "attended": 4,
                    },
                ],
            },
            {
                "name": "RoboX",
                "category": "Engineering / Robotics",
                "program_key": "btech_robotics",
                "manager": mgr_robox,
                "description": (
                    "**Building the Future of Autonomous Machines & Embedded Robotics**\n\n"
                    "• **Category:** Engineering / Robotics\n"
                    "• **Focus:** Hardware prototyping, autonomous robotics, IoT, and inter-college bot competitions.\n"
                    "• **Meeting Schedule:** Every Tuesday & Friday at 4:30 PM | Innovation Workshop (Block C, Lab 102)\n"
                    "• **Contact Email:** robox@clubsphere.edu\n"
                    "• **Key Initiatives:** ROS2 autonomous rovers, drone design, battle-bot fabrication, microcontroller prototyping, and national robotic combat circuits."
                ),
                "members": [students[1], students[8], students[0], students[4], students[14]],
                "events": [
                    {
                        "title": "Autonomous Line Follower & Maze Solver Arena",
                        "venue": "Innovation Workshop Arena (Block C)",
                        "days_offset": 16,
                        "capacity": 45,
                        "status": "published",
                    },
                    {
                        "title": "Microcontroller & Sensor Interfacing Bootcamp",
                        "venue": "Embedded Systems Lab (Block C, Room 201)",
                        "days_offset": -10,
                        "capacity": 40,
                        "status": "completed",
                        "attended": 4,
                    },
                ],
            },
            {
                "name": "FineArts",
                "category": "Arts & Culture",
                "program_key": "ba_liberal_arts",
                "manager": mgr_finearts,
                "description": (
                    "**Visual Storytelling, Aesthetic Exploration & Contemporary Creative Arts**\n\n"
                    "• **Category:** Arts & Culture\n"
                    "• **Focus:** Painting, sketching, digital illustration, campus murals, and annual art exhibitions.\n"
                    "• **Meeting Schedule:** Every Thursday at 4:00 PM | Atelier Fine Arts Studio (Block A, Studio 3)\n"
                    "• **Contact Email:** finearts@clubsphere.edu\n"
                    "• **Key Initiatives:** Live sketching walks, watercolor galleries, collaborative campus wall murals, Procreate digital masterclasses, and the Annual University Arts Gala."
                ),
                "members": [students[2], students[9], students[5], students[12]],
                "events": [
                    {
                        "title": "Campus Wall Mural & Street Art Jam",
                        "venue": "Central Amphitheatre Corridor",
                        "days_offset": 8,
                        "capacity": 35,
                        "status": "published",
                    },
                    {
                        "title": "Digital Illustration & Character Design Masterclass",
                        "venue": "Fine Arts Studio (Block A, Studio 3)",
                        "days_offset": -15,
                        "capacity": 30,
                        "status": "completed",
                        "attended": 3,
                    },
                ],
            },
            {
                "name": "Moot Court",
                "category": "Law / Debate",
                "program_key": "ballb_integrated",
                "manager": mgr_moot,
                "description": (
                    "**Fostering Rigorous Legal Advocacy, Constitutional Jurisprudence & Public Discourse**\n\n"
                    "• **Category:** Law / Debate\n"
                    "• **Focus:** Mock trial competitions, constitutional law debates, legal drafting, and public speaking.\n"
                    "• **Meeting Schedule:** Every Monday at 5:30 PM | Justice H.R. Khanna Moot Court Hall (Law Block)\n"
                    "• **Contact Email:** mootcourt@clubsphere.edu\n"
                    "• **Key Initiatives:** Appellate brief drafting, national inter-university mock trials, parliamentary debating tournaments, and judicial citation workshops."
                ),
                "members": [students[3], students[10], students[2], students[5]],
                "events": [
                    {
                        "title": "Annual National Mock Trial Invitational 2026",
                        "venue": "Moot Court Complex (Law Block, 3rd Floor)",
                        "days_offset": 24,
                        "capacity": 80,
                        "status": "published",
                    },
                    {
                        "title": "Constitutional Law Colloquium & Parliamentary Debate",
                        "venue": "Seminar Hall 1",
                        "days_offset": -22,
                        "capacity": 50,
                        "status": "completed",
                        "attended": 3,
                    },
                ],
            },
            {
                "name": "Codex",
                "category": "Technology / Programming",
                "program_key": "btech_cse",
                "manager": mgr_codex,
                "description": (
                    "**Competitive Programming, Open-Source Engineering & Software Architecture**\n\n"
                    "• **Category:** Technology / Programming\n"
                    "• **Focus:** Competitive programming, open-source contributions, web/app development, and coding bootcamps.\n"
                    "• **Meeting Schedule:** Every Saturday at 11:00 AM | Central Computing Lab 1 (Block D)\n"
                    "• **Contact Email:** codex@clubsphere.edu\n"
                    "• **Key Initiatives:** LeetCode/Codeforces weekly contest prep, ACM-ICPC regional training, Google Summer of Code mentorship, and 24-hour hack nights."
                ),
                "members": [students[4], students[11], students[14], students[0], students[1]],
                "events": [
                    {
                        "title": "Codex Algorithm Sprint & Speed Coding Blitz",
                        "venue": "Computing Lab 1 (Block D)",
                        "days_offset": 5,
                        "capacity": 75,
                        "status": "published",
                    },
                    {
                        "title": "Open Source Git & Full-Stack Architecture Boot",
                        "venue": "Computing Lab 2 (Block D)",
                        "days_offset": -12,
                        "capacity": 60,
                        "status": "completed",
                        "attended": 4,
                    },
                ],
            },
            {
                "name": "Literary",
                "category": "Literature & Media",
                "program_key": "bajmc_general",
                "manager": mgr_literary,
                "description": (
                    "**Creative Nonfiction, Spoken Word Poetry, Book Circles & Campus Journalism**\n\n"
                    "• **Category:** Literature & Media\n"
                    "• **Focus:** Creative writing, poetry slams, book clubs, campus newsletters, and editorial publishing.\n"
                    "• **Meeting Schedule:** Every Friday at 3:30 PM | University Central Library (Reading Terrace)\n"
                    "• **Contact Email:** literary@clubsphere.edu\n"
                    "• **Key Initiatives:** 'The Campus Chronicle' monthly student publication, spoken-word open mic evenings, novel dissection reading circles, and flash-fiction contests."
                ),
                "members": [students[5], students[12], students[2], students[9], students[3]],
                "events": [
                    {
                        "title": "Under the Stars: Annual Spoken Word & Poetry Slam",
                        "venue": "Library Reading Terrace & Open Lawn",
                        "days_offset": 14,
                        "capacity": 50,
                        "status": "published",
                    },
                    {
                        "title": "Creative Nonfiction & Investigative Journalism Workshop",
                        "venue": "Media Studio Room 104",
                        "days_offset": -20,
                        "capacity": 40,
                        "status": "completed",
                        "attended": 4,
                    },
                ],
            },
            {
                "name": "Bioverse",
                "category": "Science / Biotech",
                "program_key": "btech_biotech",
                "manager": mgr_bioverse,
                "description": (
                    "**Decoding Biological Systems, Genetic Innovation & Environmental Sustainability**\n\n"
                    "• **Category:** Science / Biotech\n"
                    "• **Focus:** Biotechnology, bioinformatics, environmental sustainability projects, and bio-research seminars.\n"
                    "• **Meeting Schedule:** Every Wednesday at 4:30 PM | Bio-Engineering Research Lab (Block E, Room 108)\n"
                    "• **Contact Email:** bioverse@clubsphere.edu\n"
                    "• **Key Initiatives:** Wet-lab molecular biology techniques, genomic sequence analysis, campus organic composting projects, CRISPR discussion circles, and biotech symposiums."
                ),
                "members": [students[6], students[13], students[1], students[7]],
                "events": [
                    {
                        "title": "Bioinformatics & Genomic Sequence Analysis Colloquium",
                        "venue": "Bioinformatics Lab (Block E, Room 112)",
                        "days_offset": 20,
                        "capacity": 45,
                        "status": "published",
                    },
                    {
                        "title": "Campus Bio-Composting & Zero-Waste Practical Drive",
                        "venue": "Campus Botanical Garden & Eco-Park",
                        "days_offset": -8,
                        "capacity": 50,
                        "status": "completed",
                        "attended": 3,
                    },
                ],
            },
        ]

        print("==> Upserting 7 university clubs and linking members & events...")
        seeded_clubs = []
        for spec in clubs_spec:
            club = upsert_club(
                db,
                name=spec["name"],
                program_key=spec["program_key"],
                manager=spec["manager"],
                description=spec["description"],
                status="active",
            )
            # Add member pool
            for member in spec["members"]:
                add_member_if_missing(db, club, member, role="Member")

            # Add events & registrations
            for ev in spec["events"]:
                event_obj = upsert_event(
                    db,
                    club=club,
                    title=ev["title"],
                    venue=ev["venue"],
                    days_offset=ev["days_offset"],
                    capacity=ev["capacity"],
                    status=ev["status"],
                    creator=spec["manager"],
                )
                attended_cnt = ev.get("attended", 0)
                register_users_for_event(db, event_obj, spec["members"], attended_count=attended_cnt)

            seeded_clubs.append(club)

        db.commit()

        print("\n========================================================")
        print("✓ Successfully seeded the 7 University Clubs in ClubSphere!")
        print("========================================================")
        for c in seeded_clubs:
            active_mems = (
                db.query(ClubMembership)
                .filter(ClubMembership.ClubId == c.ClubId, ClubMembership.Status == "active")
                .count()
            )
            ev_count = db.query(Event).filter(Event.ClubId == c.ClubId).count()
            print(f" • [{c.ClubId}] {c.Name:<15} | Program: {c.program.FullName:<35} | Members: {active_mems:<2} | Events: {ev_count}")

        print(f"\nDefault credentials for all seeded demo accounts:")
        print(f" • Password: {DEFAULT_PASSWORD}")
        print(" • Managers:")
        for spec in clubs_spec:
            print(f"    - {spec['name']:<12}: {spec['manager'].Email}")

    except Exception as exc:
        db.rollback()
        print(f"ERROR: Failed to seed clubs: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_clubs()
