"""add v0.2 initiative columns

Revision ID: f1e2d3c4b5a6
Revises: 3a59a07bcdd3
Create Date: 2026-08-13 20:00:00.000000

Adds the v0.2 columns to the initiatives table that were missing from
previous migrations: cluster, afdeling, team, potentie, capaciteitsvraag,
risico, bron_initiatief, externe_partners, betrokkenheid_iv,
gerelateerde_initiatieven, volgende_stap, opmerkingen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, Sequence[str], None] = '3a59a07bcdd3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Nieuwe v0.2 kolommen op de initiatives tabel
NEW_COLUMNS = {
    'cluster': sa.Text(),
    'afdeling': sa.Text(),
    'team': sa.Text(),
    'potentie': sa.Text(),
    'capaciteitsvraag': sa.Text(),
    'risico': sa.Text(),
    'bron_initiatief': sa.Text(),
    'externe_partners': sa.Text(),
    'betrokkenheid_iv': sa.Text(),
    'gerelateerde_initiatieven': sa.Text(),
    'volgende_stap': sa.Text(),
    'opmerkingen': sa.Text(),
}


def _existing_columns(table_name: str) -> set:
    """Return the set of column names on a table (empty if it doesn't exist)."""
    conn = op.get_bind()
    inspector = inspect(conn)
    if table_name not in inspector.get_table_names():
        return set()
    return {col['name'] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Add v0.2 columns to initiatives table (idempotent — skip existing)."""
    existing = _existing_columns('initiatives')
    with op.batch_alter_table('initiatives', schema=None) as batch_op:
        for col_name, col_type in NEW_COLUMNS.items():
            if col_name not in existing:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    """Remove v0.2 columns from initiatives table."""
    with op.batch_alter_table('initiatives', schema=None) as batch_op:
        batch_op.drop_column('opmerkingen')
        batch_op.drop_column('volgende_stap')
        batch_op.drop_column('gerelateerde_initiatieven')
        batch_op.drop_column('betrokkenheid_iv')
        batch_op.drop_column('externe_partners')
        batch_op.drop_column('bron_initiatief')
        batch_op.drop_column('risico')
        batch_op.drop_column('capaciteitsvraag')
        batch_op.drop_column('potentie')
        batch_op.drop_column('team')
        batch_op.drop_column('afdeling')
        batch_op.drop_column('cluster')
