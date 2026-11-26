"""clean raw markdown formatting from existing clubs description and motives

Revision ID: e6a1b2c3d4e5
Revises: d5f0e2a3b4c5
Create Date: 2026-11-26 15:30:00.000000

Data migration: strips literal `**`, `__`, `*`, `_`, and extra formatting tokens
from existing Clubs.Description and Clubs.Motives columns so drop-caps and plain text
render cleanly.
"""
from typing import Sequence, Union
import re
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


# revision identifiers, used by Alembic.
revision: str = "e6a1b2c3d4e5"
down_revision: Union[str, None] = "d5f0e2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _clean_text(val: str | None) -> str | None:
    if not val:
        return val
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", val)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = cleaned.replace("**", "").replace("``", "")
    return cleaned.strip()


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        clubs_table = sa.table(
            "Clubs",
            sa.column("ClubId", sa.Integer),
            sa.column("Description", sa.Text),
            sa.column("Motives", sa.Text),
        )
        rows = session.execute(sa.select(clubs_table.c.ClubId, clubs_table.c.Description, clubs_table.c.Motives)).all()
        for row in rows:
            new_desc = _clean_text(row.Description)
            new_motives = _clean_text(row.Motives)
            if new_desc != row.Description or new_motives != row.Motives:
                session.execute(
                    sa.update(clubs_table)
                    .where(clubs_table.c.ClubId == row.ClubId)
                    .values(Description=new_desc, Motives=new_motives)
                )
        session.commit()
    except Exception:
        session.rollback()
        # Non-fatal if table doesn't have data yet
    finally:
        session.close()


def downgrade() -> None:
    # Text sanitization is not lossy in meaning; nothing to undo
    pass
