"""initial

Revision ID: 378b2c70cc5f
Revises: 
Create Date: 2024-08-25 10:41:32.279673

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '378b2c70cc5f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('areas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('language', sa.Enum('RU', 'EN', 'HY', name='language'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    sa.UniqueConstraint('name', 'language', name='uq_area_name_language')
    )
    op.create_table('bot_users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('username', sa.String(), nullable=True),
    sa.Column('first_name', sa.String(), nullable=True),
    sa.Column('last_name', sa.String(), nullable=True),
    sa.Column('date_joined', sa.DateTime(), nullable=True),
    sa.Column('language', sa.Enum('RU', 'EN', 'HY', name='language'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.Enum('POWER', 'WATER', 'GAS', name='eventtype'), nullable=True),
    sa.Column('language', sa.Enum('RU', 'EN', 'HY', name='language'), nullable=True),
    sa.Column('area', sa.String(), nullable=True),
    sa.Column('district', sa.String(), nullable=True),
    sa.Column('house_number', sa.String(), nullable=True),
    sa.Column('start_time', sa.String(), nullable=True),
    sa.Column('end_time', sa.String(), nullable=True),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('planned', sa.Boolean(), nullable=True),
    sa.Column('processed', sa.Boolean(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('hash', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('hash', name='_event_hash_uc')
    )
    op.create_table('posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('language', sa.Enum('RU', 'EN', 'HY', name='language'), nullable=False),
    sa.Column('text', sa.String(), nullable=False),
    sa.Column('creation_time', sa.DateTime(), nullable=True),
    sa.Column('posted_time', sa.DateTime(), nullable=True),
    sa.Column('area_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['area_id'], ['areas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('subscriptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('keyword', sa.String(), nullable=False),
    sa.Column('area_id', sa.Integer(), nullable=False),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['area_id'], ['areas.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['bot_users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'area_id', 'keyword', name='_user_area_keyword_uc')
    )
    op.create_table('post_event_association',
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ),
    sa.PrimaryKeyConstraint('post_id', 'event_id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('post_event_association')
    op.drop_table('subscriptions')
    op.drop_table('posts')
    op.drop_table('events')
    op.drop_table('bot_users')
    op.drop_table('areas')
    # ### end Alembic commands ###
