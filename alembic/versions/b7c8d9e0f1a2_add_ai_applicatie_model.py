"""add ai_applicatie_model column to initiatives

Revision ID: b7c8d9e0f1a2
Revises: f1e2d3c4b5a6
Create Date: 2026-08-14 10:00:00.000000

Adds the ai_applicatie_model column (SaaS / on-premise / binnen een
applicatie) to the initiatives table, capturing how an AI application is
hosted/deployed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'f1e2d3c4b5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = {c['name'] for c in inspect(conn).get_columns('initiatives')}
    if 'ai_applicatie_model' not in columns:
        with op.batch_alter_table('initiatives', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'ai_applicatie_model',
                    sa.Enum(
                        'saas', 'on_premise', 'binnen_applicatie',
                        name='ai_applicatie_model',
                    ),
                    nullable=True,
                )
            )


def downgrade() -> None:
    with op.batch_alter_table('initiatives', schema=None) as batch_op:
        batch_op.drop_column('ai_applicatie_model')
