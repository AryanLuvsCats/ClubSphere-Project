"""Reusable object-level authorization helpers.

These functions intentionally depend only on ORM objects so they can be used
from list queries, detail endpoints, and tests without duplicating role logic.
"""
from typing import Optional

from app.models.models import (
    Club,
    ClubProposal,
    Event,
    EventOutcome,
    EventRegistration,
    RoleNameEnum,
    User,
)


PUBLIC_CLUB_STATUSES = {"active"}
PUBLIC_EVENT_STATUSES = {"published", "completed"}


def normalize_role(role_val: str) -> str:
    """Normalize role string to canonical enum value."""
    cleaned = role_val.strip().lower().replace(" ", "").replace("_", "")
    mapping = {
        "student": RoleNameEnum.STUDENT.value,
        "clubmanager": RoleNameEnum.CLUB_MANAGER.value,
        "manager": RoleNameEnum.CLUB_MANAGER.value,
        "faculty": RoleNameEnum.FACULTY.value,
        "hod": RoleNameEnum.HOD.value,
        "admin": RoleNameEnum.ADMINISTRATOR.value,
        "administrator": RoleNameEnum.ADMINISTRATOR.value,
    }
    return mapping.get(cleaned, role_val)


def role_name(user: Optional[User]) -> str:
    if not user or not user.role:
        return ""
    return normalize_role(user.role.RoleName)


def is_admin(user: Optional[User]) -> bool:
    return role_name(user) == RoleNameEnum.ADMINISTRATOR.value


def is_hod(user: Optional[User]) -> bool:
    return role_name(user) == RoleNameEnum.HOD.value


def is_faculty(user: Optional[User]) -> bool:
    return role_name(user) == RoleNameEnum.FACULTY.value


def is_reviewer(user: Optional[User]) -> bool:
    return role_name(user) in {
        RoleNameEnum.FACULTY.value,
        RoleNameEnum.HOD.value,
        RoleNameEnum.ADMINISTRATOR.value,
    }


def branch_id_for_user(user: Optional[User]) -> Optional[int]:
    if not user or not user.program:
        return None
    return user.program.BranchId


def branch_id_for_proposal(proposal: ClubProposal) -> Optional[int]:
    if not proposal.program:
        return None
    return proposal.program.BranchId


def can_manage_club(user: Optional[User], club: Club) -> bool:
    if not user:
        return False
    return is_admin(user) or club.ManagerUserId == user.UserId


def can_view_club(user: Optional[User], club: Club) -> bool:
    if club.Status in PUBLIC_CLUB_STATUSES:
        return True
    return can_manage_club(user, club)


def can_manage_event(user: Optional[User], event: Event) -> bool:
    if not user:
        return False
    return is_admin(user) or (
        event.club is not None and event.club.ManagerUserId == user.UserId
    )


def can_view_event(user: Optional[User], event: Event) -> bool:
    if event.Status in PUBLIC_EVENT_STATUSES:
        return True
    return can_manage_event(user, event)


def can_view_proposal(user: Optional[User], proposal: ClubProposal) -> bool:
    if not user:
        return False
    if is_admin(user) or proposal.ApplicantUserId == user.UserId:
        return True
    if role_name(user) in {
        RoleNameEnum.FACULTY.value,
        RoleNameEnum.HOD.value,
    }:
        user_branch = branch_id_for_user(user)
        return user_branch is not None and user_branch == branch_id_for_proposal(proposal)
    return False


def can_review_proposal(user: Optional[User], proposal: ClubProposal) -> bool:
    if not user:
        return False
    # Never allow a user to review their own proposal, even an administrator.
    if proposal.ApplicantUserId == user.UserId:
        return False
    if is_admin(user):
        return True
    if role_name(user) not in {RoleNameEnum.FACULTY.value, RoleNameEnum.HOD.value}:
        return False
    user_branch = branch_id_for_user(user)
    return user_branch is not None and user_branch == branch_id_for_proposal(proposal)


def can_view_event_outcome(
    user: Optional[User],
    event: Event,
    outcome: EventOutcome,
    db,
) -> bool:
    if not user:
        return False
    if can_manage_event(user, event):
        return True
    return (
        db.query(EventRegistration)
        .filter(
            EventRegistration.EventId == event.EventId,
            EventRegistration.UserId == user.UserId,
            EventRegistration.Status != "cancelled",
        )
        .first()
        is not None
    )
