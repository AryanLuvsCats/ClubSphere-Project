"""auth sessions and brute-force throttle

Revision ID: c4e9a1b2d3f4
Revises: b3df5d5ed152
Create Date: 2026-11-04 00:00:00.000000

Additive migration only: creates RefreshSessions and AuthThrottle.
No existing table, column, or row is modified or deleted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4e9a1b2d3f4"
down_revision: Union[str, None] = "b3df5d5ed152"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "RefreshSessions",
        sa.Column("SessionId", sa.String(length=64), nullable=False),
        sa.Column("UserId", sa.Integer(), nullable=False),
        sa.Column("FamilyId", sa.String(length=64), nullable=False),
        sa.Column("TokenHash", sa.String(length=64), nullable=False),
        sa.Column("IssuedAt", sa.DateTime(), nullable=False),
        sa.Column("ExpiresAt", sa.DateTime(), nullable=False),
        sa.Column("RevokedAt", sa.DateTime(), nullable=True),
        sa.Column("ReplacedBySessionId", sa.String(length=64), nullable=True),
        sa.Column("ReplacedAt", sa.DateTime(), nullable=True),
        sa.Column("IpAddress", sa.String(length=45), nullable=True),
        sa.Column("UserAgent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["UserId"], ["Users.UserId"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("SessionId"),
    )
    op.create_index(
        op.f("ix_RefreshSessions_SessionId"),
        "RefreshSessions",
        ["SessionId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_RefreshSessions_UserId"),
        "RefreshSessions",
        ["UserId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_RefreshSessions_FamilyId"),
        "RefreshSessions",
        ["FamilyId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_RefreshSessions_TokenHash"),
        "RefreshSessions",
        ["TokenHash"],
        unique=True,
    )
    op.create_index(
        "IX_RefreshSessions_UserId_FamilyId",
        "RefreshSessions",
        ["UserId", "FamilyId"],
        unique=False,
    )
    op.create_index(
        "IX_RefreshSessions_ExpiresAt",
        "RefreshSessions",
        ["ExpiresAt"],
        unique=False,
    )

    op.create_table(
        "AuthThrottle",
        sa.Column("ThrottleId", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("Scope", sa.String(length=32), nullable=False),
        sa.Column("KeyHash", sa.String(length=64), nullable=False),
        sa.Column("FailureCount", sa.Integer(), nullable=False),
        sa.Column("WindowStartedAt", sa.DateTime(), nullable=False),
        sa.Column("BlockedUntil", sa.DateTime(), nullable=True),
        sa.Column("UpdatedAt", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("ThrottleId"),
        sa.UniqueConstraint(
            "Scope",
            "KeyHash",
            name="UQ_AuthThrottle_Scope_Key",
        ),
    )
    op.create_index(
        op.f("ix_AuthThrottle_ThrottleId"),
        "AuthThrottle",
        ["ThrottleId"],
        unique=False,
    )
    op.create_index(
        "IX_AuthThrottle_BlockedUntil",
        "AuthThrottle",
        ["BlockedUntil"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("IX_AuthThrottle_BlockedUntil", table_name="AuthThrottle")
    op.drop_index(op.f("ix_AuthThrottle_ThrottleId"), table_name="AuthThrottle")
    op.drop_table("AuthThrottle")

    op.drop_index("IX_RefreshSessions_ExpiresAt", table_name="RefreshSessions")
    op.drop_index(
        "IX_RefreshSessions_UserId_FamilyId",
        table_name="RefreshSessions",
    )
    op.drop_index(op.f("ix_RefreshSessions_TokenHash"), table_name="RefreshSessions")
    op.drop_index(op.f("ix_RefreshSessions_FamilyId"), table_name="RefreshSessions")
    op.drop_index(op.f("ix_RefreshSessions_UserId"), table_name="RefreshSessions")
    op.drop_index(op.f("ix_RefreshSessions_SessionId"), table_name="RefreshSessions")
    op.drop_table("RefreshSessions")
