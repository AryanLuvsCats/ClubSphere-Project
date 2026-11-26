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
_CACHED_PASSWORD_HASH = None


def get_cached_password_hash() -> str:
    global _CACHED_PASSWORD_HASH
    if _CACHED_PASSWORD_HASH is None:
        _CACHED_PASSWORD_HASH = get_password_hash(DEFAULT_PASSWORD)
    return _CACHED_PASSWORD_HASH


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
        PasswordHash=get_cached_password_hash(),
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
    motives: str | None = None,
    past_achievements: list[dict] | None = None,
    leadership_contacts: list[dict] | None = None,
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
        if motives is not None:
            club.Motives = motives
        if past_achievements is not None:
            club.PastAchievements = past_achievements
        if leadership_contacts is not None:
            club.LeadershipContacts = leadership_contacts
        db.flush()
    else:
        club = Club(
            Name=name,
            ProgramId=prog.ProgramId,
            ManagerUserId=manager.UserId,
            Description=description,
            Motives=motives,
            PastAchievements=past_achievements or [],
            LeadershipContacts=leadership_contacts or [],
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
                "motives": (
                    "To democratize Artificial Intelligence education, foster interdisciplinary machine learning research, "
                    "and train students in generative AI, deep neural networks, and ethical computation. We bridge the gap between "
                    "classroom mathematics and real-world deployment through industry-partnered projects, Kaggle sprints, and open-source models."
                ),
                "past_achievements": [
                    {
                        "title": "Smart India Hackathon National Champions",
                        "date": "Nov 2025",
                        "description": "Won 1st Place in the AI & Computer Vision category by building an automated multimodal crop disease diagnostic platform.",
                        "award_or_highlight": "1st Place & ₹1,00,000 Cash Prize",
                    },
                    {
                        "title": "Kaggle LLM Benchmark Grandmaster Sprint",
                        "date": "Aug 2025",
                        "description": "Ranked in the top 1.5% globally in the Kaggle Open-Source LLM Fine-Tuning and Model Distillation competition.",
                        "award_or_highlight": "Kaggle Gold Medalist Finish",
                    },
                    {
                        "title": "Annual Campus AI Symposium 2026",
                        "date": "Jan 2026",
                        "description": "Hosted 450+ delegates and presented 8 peer-reviewed research papers in collaboration with top industry lab scientists.",
                        "award_or_highlight": "Best Campus Technical Symposium",
                    },
                ],
                "leadership_contacts": [
                    {
                        "role": "President",
                        "name": "Aarav Sharma",
                        "email": "aarav.sharma@clubsphere.edu",
                        "phone": "+91 98765 43210",
                    },
                    {
                        "role": "Vice President",
                        "name": "Sneha Verma",
                        "email": "sneha.verma@clubsphere.edu",
                        "phone": "+91 98765 43211",
                    },
                    {
                        "role": "Media Head",
                        "name": "Dev Patel",
                        "email": "dev.patel@clubsphere.edu",
                        "phone": "+91 98765 43212",
                    },
                    {
                        "role": "Tech Head",
                        "name": "Kabir Mehta",
                        "email": "kabir.mehta@clubsphere.edu",
                        "phone": "+91 98765 43213",
                    },
                ],
                "description": (
                    "Pioneering Artificial Intelligence, Machine Learning & Intelligent Systems.\n\n"
                    "• Category: Technology / AI\n"
                    "• Focus: Artificial Intelligence, Machine Learning, deep learning workshops, and data science hackathons.\n"
                    "• Meeting Schedule: Every Wednesday at 5:00 PM | Turing AI Research Lab (Block B, Room 204)\n"
                    "• Contact Email: aiml.club@clubsphere.edu\n"
                    "• Key Initiatives: Weekly research paper reviews, Kaggle sprint competitions, PyTorch/TensorFlow bootcamps, and foundational Generative AI workshops."
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
                    {
                        "title": "Generative AI Bootcamp: Fine-Tuning LLMs on Custom Data",
                        "venue": "Computing Lab 4 (Block B)",
                        "days_offset": -40,
                        "capacity": 80,
                        "status": "completed",
                        "attended": 5,
                    },
                ],
            },
            {
                "name": "RoboX",
                "category": "Engineering / Robotics",
                "program_key": "btech_robotics",
                "manager": mgr_robox,
                "motives": (
                    "To empower students in hardware fabrication, autonomous navigation, embedded robotics, and ROS2 systems. "
                    "RoboX cultivates hands-on engineering instincts by designing combat-ready battlebots, autonomous rovers, "
                    "and multi-rotor UAV systems that compete at national engineering exhibitions."
                ),
                "past_achievements": [
                    {
                        "title": "IIT Techfest Robowars Champions",
                        "date": "Dec 2025",
                        "description": "Dominant 1st place in the national 30kg combat robotics heavyweight championship.",
                        "award_or_highlight": "National Robowars Gold Trophy & ₹1,50,000",
                    },
                    {
                        "title": "Autonomous Rover Challenge",
                        "date": "Sep 2025",
                        "description": "Designed and tested a fully autonomous GPS-guided terrain rover with LiDAR obstacle avoidance.",
                        "award_or_highlight": "Best Autonomous Hardware Design",
                    },
                    {
                        "title": "Campus Maker Faire Showcase",
                        "date": "Jan 2026",
                        "description": "Demonstrated 12 custom robotic prototypes to over 2,000 university students and visiting school groups.",
                        "award_or_highlight": "Excellence in Engineering Outreach",
                    },
                ],
                "leadership_contacts": [
                    {
                        "role": "President",
                        "name": "Vikramaditya Rao",
                        "email": "lead.robox@clubsphere.edu",
                        "phone": "+91 98765 43220",
                    },
                    {
                        "role": "Vice President",
                        "name": "Ananya Iyer",
                        "email": "ananya.iyer@clubsphere.edu",
                        "phone": "+91 98765 43221",
                    },
                    {
                        "role": "Media Head",
                        "name": "Tanmay Bhatia",
                        "email": "tanmay.bhatia@clubsphere.edu",
                        "phone": "+91 98765 43222",
                    },
                    {
                        "role": "Tech Head",
                        "name": "Aditya Joshi",
                        "email": "aditya.joshi@clubsphere.edu",
                        "phone": "+91 98765 43223",
                    },
                ],
                "description": (
                    "Building the Future of Autonomous Machines & Embedded Robotics.\n\n"
                    "• Category: Engineering / Robotics\n"
                    "• Focus: Hardware prototyping, autonomous robotics, IoT, and inter-college bot competitions.\n"
                    "• Meeting Schedule: Every Tuesday & Friday at 4:30 PM | Innovation Workshop (Block C, Lab 102)\n"
                    "• Contact Email: robox@clubsphere.edu\n"
                    "• Key Initiatives: ROS2 autonomous rovers, drone design, battle-bot fabrication, microcontroller prototyping, and national robotic combat circuits."
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
                    {
                        "title": "Combat Robot Teardown & Armor Fabrication Clinic",
                        "venue": "Machine Workshop (Block C, Bay 3)",
                        "days_offset": -35,
                        "capacity": 35,
                        "status": "completed",
                        "attended": 3,
                    },
                ],
            },
            {
                "name": "FineArts",
                "category": "Arts & Culture",
                "program_key": "ba_liberal_arts",
                "manager": mgr_finearts,
                "motives": (
                    "To celebrate creative self-expression, studio painting, digital illustration, and campus aesthetic culture. "
                    "FineArts provides an inspiring sanctuary for student artists of all majors to explore mediums from watercolor and oil "
                    "to digital concept art and large-scale architectural murals."
                ),
                "past_achievements": [
                    {
                        "title": "State University Art Biennial Gold",
                        "date": "Nov 2025",
                        "description": "Won 1st prize in contemporary oil painting and mixed-media installation with our collective student canvas.",
                        "award_or_highlight": "Governor's Gold Medal for Visual Arts",
                    },
                    {
                        "title": "Campus Heritage 200ft Mural Installation",
                        "date": "Oct 2025",
                        "description": "Designed and executed a vibrant 200-foot heritage mural celebrating Indian cultural diversity in the central walkway.",
                        "award_or_highlight": "University Campus Beautification Award",
                    },
                    {
                        "title": "Annual Student Spring Art Gala",
                        "date": "Feb 2026",
                        "description": "Showcased 90 original student artworks and auctioned student pieces for charity, raising over ₹1,20,000.",
                        "award_or_highlight": "Outstanding Cultural Initiative",
                    },
                ],
                "leadership_contacts": [
                    {
                        "role": "President",
                        "name": "Sunaina Kashyap",
                        "email": "lead.finearts@clubsphere.edu",
                        "phone": "+91 98765 43230",
                    },
                    {
                        "role": "Vice President",
                        "name": "Zara Khan",
                        "email": "zara.khan@clubsphere.edu",
                        "phone": "+91 98765 43231",
                    },
                    {
                        "role": "Media Head",
                        "name": "Meera Nair",
                        "email": "meera.nair@clubsphere.edu",
                        "phone": "+91 98765 43232",
                    },
                    {
                        "role": "Tech Head",
                        "name": "Dev Patel",
                        "email": "dev.patel@clubsphere.edu",
                        "phone": "+91 98765 43233",
                    },
                ],
                "description": (
                    "Visual Storytelling, Aesthetic Exploration & Contemporary Creative Arts.\n\n"
                    "• Category: Arts & Culture\n"
                    "• Focus: Painting, sketching, digital illustration, campus murals, and annual art exhibitions.\n"
                    "• Meeting Schedule: Every Thursday at 4:00 PM | Atelier Fine Arts Studio (Block A, Studio 3)\n"
                    "• Contact Email: finearts@clubsphere.edu\n"
                    "• Key Initiatives: Live sketching walks, watercolor galleries, collaborative campus wall murals, Procreate digital masterclasses, and the Annual University Arts Gala."
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
                    {
                        "title": "Plein Air Watercolor Workshop on the Lawn",
                        "venue": "Campus Botanical Garden Terrace",
                        "days_offset": -30,
                        "capacity": 25,
                        "status": "completed",
                        "attended": 4,
                    },
                ],
            },
            {
                "name": "Moot Court",
                "category": "Law / Debate",
                "program_key": "ballb_integrated",
                "manager": mgr_moot,
                "motives": (
                    "To hone courtroom advocacy, constitutional jurisprudence, appellate drafting, and ethical rhetoric. "
                    "Moot Court prepares aspiring legal scholars to deconstruct complex statutes, examine legal precedents, "
                    "and compete with distinction in national and international simulated trials."
                ),
                "past_achievements": [
                    {
                        "title": "National Moot Court Competition Best Memorial",
                        "date": "Oct 2025",
                        "description": "Awarded Best Memorial and Runner-up Advocates in the prestigious National Constitutional Law Challenge.",
                        "award_or_highlight": "Best Memorial & Runner-Up Trophy",
                    },
                    {
                        "title": "All-India Parliamentary Debate Winners",
                        "date": "Dec 2025",
                        "description": "Undefeated champion delegation across 28 leading university law schools in Asian Parliamentary debate.",
                        "award_or_highlight": "Best Delegation Cup 2025",
                    },
                    {
                        "title": "Pro-Bono Community Legal Aid Camp",
                        "date": "Feb 2026",
                        "description": "Conducted legal literacy workshops and rights counseling for over 400 underprivileged families.",
                        "award_or_highlight": "Civic Justice & Leadership Citation",
                    },
                ],
                "leadership_contacts": [
                    {
                        "role": "President",
                        "name": "Adv. Siddharth Sen",
                        "email": "lead.mootcourt@clubsphere.edu",
                        "phone": "+91 98765 43240",
                    },
                    {
                        "role": "Vice President",
                        "name": "Ishita Gupta",
                        "email": "ishita.gupta@clubsphere.edu",
                        "phone": "+91 98765 43241",
                    },
                    {
                        "role": "Media Head",
                        "name": "Ritik Choudhary",
                        "email": "ritik.choudhary@clubsphere.edu",
                        "phone": "+91 98765 43242",
                    },
                    {
                        "role": "Tech Head",
                        "name": "Diya Sen",
                        "email": "diya.sen@clubsphere.edu",
                        "phone": "+91 98765 43243",
                    },
                ],
                "description": (
                    "Fostering Rigorous Legal Advocacy, Constitutional Jurisprudence & Public Discourse.\n\n"
                    "• Category: Law / Debate\n"
                    "• Focus: Mock trial competitions, constitutional law debates, legal drafting, and public speaking.\n"
                    "• Meeting Schedule: Every Monday at 5:30 PM | Justice H.R. Khanna Moot Court Hall (Law Block)\n"
                    "• Contact Email: mootcourt@clubsphere.edu\n"
                    "• Key Initiatives: Appellate brief drafting, national inter-university mock trials, parliamentary debating tournaments, and judicial citation workshops."
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
                        "venue": "Seminar Hall 1 (Law Block)",
                        "days_offset": -22,
                        "capacity": 50,
                        "status": "completed",
                        "attended": 3,
                    },
                    {
                        "title": "Memorial Drafting & Legal Research Workshop",
                        "venue": "Law Library Discussion Suite",
                        "days_offset": -45,
                        "capacity": 40,
                        "status": "completed",
                        "attended": 4,
                    },
                ],
            },
            {
                "name": "Codex",
                "category": "Technology / Programming",
                "program_key": "btech_cse",
                "manager": mgr_codex,
                "motives": (
                    "To cultivate world-class software engineering habits, algorithmic mastery, open-source contribution, "
                    "and systems design. Codex unites competitive coders, kernel tinkerers, and full-stack builders through intense "
                    "hackathons, code reviews, and distributed systems sprints."
                ),
                "past_achievements": [
                    {
                        "title": "ACM-ICPC Regional Finalist Qualification",
                        "date": "Dec 2025",
                        "description": "Two university teams placed in the top 12 in the Asia-Amritapuri ICPC Regional Contest.",
                        "award_or_highlight": "Top 12 Regional Rank",
                    },
                    {
                        "title": "HackCodex 36-Hour National Hackathon",
                        "date": "Jan 2026",
                        "description": "Organized the premier campus hackathon with 600+ developers, 8 sponsor tracks, and ₹5,00,000 in prizes.",
                        "award_or_highlight": "Flagship Hackathon of the Year",
                    },
                    {
                        "title": "Open Source Summer Contribution Drive",
                        "date": "Jul 2025",
                        "description": "Merged 145+ pull requests into prominent CNCF, Apache, and Mozilla open-source repositories.",
                        "award_or_highlight": "Global Open Source Recognition",
                    },
                ],
                "leadership_contacts": [
                    {
                        "role": "President",
                        "name": "Karthik Sundaram",
                        "email": "lead.codex@clubsphere.edu",
                        "phone": "+91 98765 43250",
                    },
                    {
                        "role": "Vice President",
                        "name": "Priya Singh",
                        "email": "priya.singh@clubsphere.edu",
                        "phone": "+91 98765 43251",
                    },
                    {
                        "role": "Media Head",
                        "name": "Arjun Kapoor",
                        "email": "arjun.kapoor@clubsphere.edu",
                        "phone": "+91 98765 43252",
                    },
                    {
                        "role": "Tech Head",
                        "name": "Kabir Mehta",
                        "email": "kabir.mehta@clubsphere.edu",
                        "phone": "+91 98765 43253",
                    },
                ],
                "description": (
                    "Competitive Programming, Open-Source Engineering & Software Architecture.\n\n"
                    "• Category: Technology / Programming\n"
                    "• Focus: Competitive programming, open-source contributions, web/app development, and coding bootcamps.\n"
                    "• Meeting Schedule: Every Saturday at 11:00 AM | Central Computing Lab 1 (Block D)\n"
                    "• Contact Email: codex@clubsphere.edu\n"
                    "• Key Initiatives: LeetCode/Codeforces weekly contest prep, ACM-ICPC regional training, Google Summer of Code mentorship, and 24-hour hack nights."
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
                    {
                        "title": "Microservices & Distributed Systems Masterclass",
                        "venue": "Computing Lab 3 (Block D)",
                        "days_offset": -38,
                        "capacity": 55,
                        "status": "completed",
                        "attended": 5,
                    },
                ],
            },
            {
                "name": "Literary",
                "category": "Literature & Media",
                "program_key": "bajmc_general",
                "manager": mgr_literary,
                "motives": (
                    "To champion the transformative art of words, investigative journalism, spoken poetry, and literary critique. "
                    "Literary serves as the university's intellectual conscience, publishing student journalism, hosting vibrant poetry slams, "
                    "and providing thoughtful spaces for critical discourse."
                ),
                "past_achievements": [
                    {
                        "title": "National Inter-University Poetry Laureate",
                        "date": "Nov 2025",
                        "description": "Secured 1st and 3rd place in the National Spoken Word & Slam Poetry Invitational in New Delhi.",
                        "award_or_highlight": "National Slam Poetry Champions",
                    },
                    {
                        "title": "The Campus Chronicle Annual Anthology",
                        "date": "Dec 2025",
                        "description": "Published a 140-page print anthology featuring student fiction, investigative campus essays, and photojournalism.",
                        "award_or_highlight": "Best Collegiate Publication",
                    },
                    {
                        "title": "Three-Day Winter Literature Conclave",
                        "date": "Feb 2026",
                        "description": "Curated an acclaimed festival hosting 14 visiting authors, journalists, and poets for masterclasses and panels.",
                        "award_or_highlight": "Campus Culture Leadership Award",
                    },
                ],
                "leadership_contacts": [
                    {
                        "role": "President",
                        "name": "Nandini Mukherjee",
                        "email": "lead.literary@clubsphere.edu",
                        "phone": "+91 98765 43260",
                    },
                    {
                        "role": "Vice President",
                        "name": "Meera Nair",
                        "email": "meera.nair@clubsphere.edu",
                        "phone": "+91 98765 43261",
                    },
                    {
                        "role": "Media Head",
                        "name": "Aditya Joshi",
                        "email": "aditya.joshi@clubsphere.edu",
                        "phone": "+91 98765 43262",
                    },
                    {
                        "role": "Tech Head",
                        "name": "Zara Khan",
                        "email": "zara.khan@clubsphere.edu",
                        "phone": "+91 98765 43263",
                    },
                ],
                "description": (
                    "Creative Nonfiction, Spoken Word Poetry, Book Circles & Campus Journalism.\n\n"
                    "• Category: Literature & Media\n"
                    "• Focus: Creative writing, poetry slams, book clubs, campus newsletters, and editorial publishing.\n"
                    "• Meeting Schedule: Every Friday at 3:30 PM | University Central Library (Reading Terrace)\n"
                    "• Contact Email: literary@clubsphere.edu\n"
                    "• Key Initiatives: 'The Campus Chronicle' monthly student publication, spoken-word open mic evenings, novel dissection reading circles, and flash-fiction contests."
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
                    {
                        "title": "Classic Fiction Book Reading & Critical Review Circle",
                        "venue": "Central Library Terrace Suite",
                        "days_offset": -42,
                        "capacity": 30,
                        "status": "completed",
                        "attended": 3,
                    },
                ],
            },
            {
                "name": "Bioverse",
                "category": "Science / Biotech",
                "program_key": "btech_biotech",
                "manager": mgr_bioverse,
                "motives": (
                    "To pioneer scientific inquiry into genomic innovation, molecular biosensing, computational biology, "
                    "and campus ecological sustainability. Bioverse empowers student researchers to synthesize modern biotechnology "
                    "solutions that address global healthcare and planetary conservation challenges."
                ),
                "past_achievements": [
                    {
                        "title": "iGEM Regional Bio-Design Bronze Medal",
                        "date": "Oct 2025",
                        "description": "Engineered an enzymatic bacterial biosensor for rapid microplastic detection in university water reservoirs.",
                        "award_or_highlight": "iGEM Asia-Pacific Bronze Award",
                    },
                    {
                        "title": "FastBio Computational Genomics Sprint",
                        "date": "Aug 2025",
                        "description": "Developed an open-source biological sequence alignment acceleration pipeline yielding 4.2x faster search times.",
                        "award_or_highlight": "Best Bioinformatics Open Innovation",
                    },
                    {
                        "title": "Campus Sustainability & Carbon Offset Audit",
                        "date": "Jan 2026",
                        "description": "Conducted comprehensive biological biodiversity and soil health mapping across 50 acres of university grounds.",
                        "award_or_highlight": "University Green Campus Trophy",
                    },
                ],
                "leadership_contacts": [
                    {
                        "role": "President",
                        "name": "Dr. Shalini Menon",
                        "email": "lead.bioverse@clubsphere.edu",
                        "phone": "+91 98765 43270",
                    },
                    {
                        "role": "Vice President",
                        "name": "Rohan Deshmukh",
                        "email": "rohan.deshmukh@clubsphere.edu",
                        "phone": "+91 98765 43271",
                    },
                    {
                        "role": "Media Head",
                        "name": "Diya Sen",
                        "email": "diya.sen@clubsphere.edu",
                        "phone": "+91 98765 43272",
                    },
                    {
                        "role": "Tech Head",
                        "name": "Ananya Iyer",
                        "email": "ananya.iyer@clubsphere.edu",
                        "phone": "+91 98765 43273",
                    },
                ],
                "description": (
                    "Decoding Biological Systems, Genetic Innovation & Environmental Sustainability.\n\n"
                    "• Category: Science / Biotech\n"
                    "• Focus: Biotechnology, bioinformatics, environmental sustainability projects, and bio-research seminars.\n"
                    "• Meeting Schedule: Every Wednesday at 4:30 PM | Bio-Engineering Research Lab (Block E, Room 108)\n"
                    "• Contact Email: bioverse@clubsphere.edu\n"
                    "• Key Initiatives: Wet-lab molecular biology techniques, genomic sequence analysis, campus organic composting projects, CRISPR discussion circles, and biotech symposiums."
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
                    {
                        "title": "CRISPR Genome Editing & Bioethics Round Table",
                        "venue": "Biotech Seminar Room 202",
                        "days_offset": -32,
                        "capacity": 40,
                        "status": "completed",
                        "attended": 4,
                    },
                ],
            },
        ]

        print("==> Upserting 7 university clubs and linking members & events...")
        seeded_clubs = []
        for spec in clubs_spec:
            print(f" -> Upserting club: {spec['name']}...")
            club = upsert_club(
                db,
                name=spec["name"],
                program_key=spec["program_key"],
                manager=spec["manager"],
                description=spec["description"],
                status="active",
                motives=spec.get("motives"),
                past_achievements=spec.get("past_achievements"),
                leadership_contacts=spec.get("leadership_contacts"),
            )
            # Add member pool
            for member in spec["members"]:
                add_member_if_missing(db, club, member, role="Member")

            # Ensure core leadership accounts and memberships
            for contact in spec.get("leadership_contacts", []):
                core_u = get_or_create_user(
                    db,
                    email=contact["email"],
                    full_name=contact["name"],
                    role_name=RoleNameEnum.STUDENT.value,
                    program_key=spec["program_key"],
                )
                existing_mem = (
                    db.query(ClubMembership)
                    .filter(
                        ClubMembership.ClubId == club.ClubId,
                        ClubMembership.UserId == core_u.UserId,
                    )
                    .first()
                )
                if existing_mem:
                    existing_mem.Role = contact["role"]
                    existing_mem.Status = "active"
                else:
                    db.add(
                        ClubMembership(
                            ClubId=club.ClubId,
                            UserId=core_u.UserId,
                            Status="active",
                            Role=contact["role"],
                            JoinedAt=utc_naive(days_offset=-25),
                        )
                    )
                db.flush()

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

            db.commit()
            seeded_clubs.append(club)

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
