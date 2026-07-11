"""add curation_narratives table

Revision ID: a1b2c3d4e5f6
Revises: 79ec42ad9b26
Create Date: 2026-07-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '79ec42ad9b26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'curation_narratives',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('curation_id', sa.String(length=36), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['curation_id'], ['curations.id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    op.drop_table('curation_narratives')
