"""add planned field to processed events table

Revision ID: 56258b59e590
Revises: ba04c31a1fa1
Create Date: 2024-08-10 21:06:51.213531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56258b59e590'
down_revision: Union[str, None] = 'ba04c31a1fa1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('processed_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('planned', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('processed_events', schema=None) as batch_op:
        batch_op.drop_column('planned')

    # ### end Alembic commands ###
