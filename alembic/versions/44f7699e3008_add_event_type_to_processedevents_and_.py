"""Add event_type to ProcessedEvents and rename table

Revision ID: 44f7699e3008
Revises: 051b156c09fa
Create Date: 2024-08-09 20:47:58.270361

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44f7699e3008'
down_revision: Union[str, None] = '051b156c09fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('processed_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.String(), nullable=False),
    sa.Column('area', sa.String(), nullable=True),
    sa.Column('district', sa.String(), nullable=True),
    sa.Column('house_numbers', sa.Text(), nullable=False),
    sa.Column('language', sa.Enum('RU', 'EN', 'AM', name='language'), nullable=False),
    sa.Column('event_type', sa.Enum('POWER', 'WATER', 'GAS', name='eventtype'), nullable=False),
    sa.Column('sent', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('start_time', 'area', 'district', 'language', name='_unique_agg_event')
    )
    op.drop_table('aggregated_events')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('aggregated_events',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('start_time', sa.VARCHAR(), nullable=False),
    sa.Column('area', sa.VARCHAR(), nullable=False),
    sa.Column('district', sa.VARCHAR(), nullable=True),
    sa.Column('house_numbers', sa.VARCHAR(), nullable=False),
    sa.Column('language', sa.VARCHAR(length=2), nullable=False),
    sa.Column('sent', sa.BOOLEAN(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('start_time', 'area', 'district', 'language', name='_unique_agg_event')
    )
    op.drop_table('processed_events')
    # ### end Alembic commands ###
