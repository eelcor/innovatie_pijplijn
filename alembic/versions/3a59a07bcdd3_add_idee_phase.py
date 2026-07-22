"""add_idee_phase

Revision ID: 3a59a07bcdd3
Revises: ce68ec0258d5
Create Date: 2026-07-13 11:43:40.768035

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a59a07bcdd3'
down_revision: Union[str, Sequence[str], None] = 'ce68ec0258d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'idee' as the first phase in the innovation pipeline.

    SQLite stores ENUMs as TEXT, so adding a new valid value does not
    require an ALTER TABLE.  The model default changes from
    'verkenning' to 'idee' — existing rows keep their current value,
    only newly created initiatives will default to 'idee'.
    """
    pass


def downgrade() -> None:
    """Remove 'idee' phase.

    Any initiative still in the 'idee' phase should be moved back to
    'verkenning' before running this downgrade.
    """
    from sqlalchemy import text
    op.execute(text("UPDATE initiatives SET phase = 'verkenning' WHERE phase = 'idee'"))
