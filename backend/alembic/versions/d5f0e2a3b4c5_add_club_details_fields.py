"""add club details fields (motives, past achievements, leadership contacts)

Revision ID: d5f0e2a3b4c5
Revises: c4e9a1b2d3f4
Create Date: 2026-11-25 00:00:00.000000

Additive migration: adds Motives, PastAchievements, and LeadershipContacts columns to Clubs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


# revision identifiers, used by Alembic.
revision: str = "d5f0e2a3b4c5"
down_revision: Union[str, None] = "c4e9a1b2d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("Clubs", sa.Column("Motives", sa.Text().with_variant(mssql.NVARCHAR(None), "mssql"), nullable=True))
    op.add_column("Clubs", sa.Column("PastAchievements", sa.JSON(), nullable=True))
    op.add_column("Clubs", sa.Column("LeadershipContacts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("Clubs", "LeadershipContacts")
    op.drop_column("Clubs", "PastAchievements")
    op.drop_column("Clubs", "Motives")
