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


# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, Sequence[str], None] = '3a59a07bcdd3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add v0.2 columns to initiatives table."""
    with op.batch_alter_table('initiatives', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cluster', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('afdeling', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('team', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('potentie', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('capaciteitsvraag', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('risico', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('bron_initiatief', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('externe_partners', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('betrokkenheid_iv', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('gerelateerde_initiatieven', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('volgende_stap', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('opmerkingen', sa.Text(), nullable=True))


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
