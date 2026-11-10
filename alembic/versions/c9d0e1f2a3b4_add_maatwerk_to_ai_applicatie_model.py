"""add maatwerk to ai_applicatie_model enum

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-08-14 11:00:00.000000

Adds the "maatwerk" (bespoke) option to the ai_applicatie_model column on
the initiatives table. On SQLite this recreates the table via batch mode to
update the column's CHECK constraint.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('initiatives', schema=None) as batch_op:
        batch_op.alter_column(
            'ai_applicatie_model',
            nullable=True,
            existing_type=sa.Enum(
                'saas', 'on_premise', 'binnen_applicatie',
                name='ai_applicatie_model',
            ),
            type_=sa.Enum(
                'saas', 'on_premise', 'binnen_applicatie', 'maatwerk',
                name='ai_applicatie_model',
            ),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('initiatives', schema=None) as batch_op:
        batch_op.alter_column(
            'ai_applicatie_model',
            nullable=True,
            existing_type=sa.Enum(
                'saas', 'on_premise', 'binnen_applicatie', 'maatwerk',
                name='ai_applicatie_model',
            ),
            type_=sa.Enum(
                'saas', 'on_premise', 'binnen_applicatie',
                name='ai_applicatie_model',
            ),
            existing_nullable=True,
        )
