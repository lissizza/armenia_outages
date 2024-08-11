"""Initial migration

Revision ID: 5c08cb2c4485
Revises: 
Create Date: 2024-08-11 14:22:02.283189

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c08cb2c4485'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.Enum('POWER', 'WATER', 'GAS', name='eventtype'), nullable=True),
    sa.Column('language', sa.Enum('RU', 'EN', 'AM', name='language'), nullable=True),
    sa.Column('area', sa.String(), nullable=True),
    sa.Column('district', sa.String(), nullable=True),
    sa.Column('house_number', sa.String(), nullable=True),
    sa.Column('start_time', sa.String(), nullable=True),
    sa.Column('end_time', sa.String(), nullable=True),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('planned', sa.Boolean(), nullable=True),
    sa.Column('processed', sa.Boolean(), nullable=True),
    sa.Column('timestamp', sa.String(), nullable=True),
    sa.Column('hash', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('hash', name='_event_hash_uc')
    )
    op.create_table('last_page',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=True),
    sa.Column('language', sa.Enum('RU', 'EN', 'AM', name='language'), nullable=True),
    sa.Column('planned', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('processed_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.Enum('POWER', 'WATER', 'GAS', name='eventtype'), nullable=False),
    sa.Column('language', sa.Enum('RU', 'EN', 'AM', name='language'), nullable=False),
    sa.Column('area', sa.String(), nullable=True),
    sa.Column('district', sa.String(), nullable=True),
    sa.Column('house_numbers', sa.Text(), nullable=True),
    sa.Column('start_time', sa.String(), nullable=True),
    sa.Column('end_time', sa.String(), nullable=True),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('planned', sa.Boolean(), nullable=True),
    sa.Column('timestamp', sa.String(), nullable=True),
    sa.Column('sent', sa.Boolean(), nullable=True),
    sa.Column('sent_time', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('start_time', 'area', 'district', 'language', name='_unique_agg_event')
    )
    op.create_table('subscriptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('keyword', sa.String(), nullable=True),
    sa.Column('language', sa.Enum('RU', 'EN', 'AM', name='language'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('subscriptions')
    op.drop_table('processed_events')
    op.drop_table('last_page')
    op.drop_table('events')
    # ### end Alembic commands ###
