"""migrate_to_asyncpg

Revision ID: 76c4237dd5e3
Revises: 2de134b10f42
Create Date: 2024-10-21 16:56:40.960756

"""

import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "76c4237dd5e3"
down_revision: Union[str, None] = "2de134b10f42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

db_user = os.getenv("POSTGRES_USER", "admin")


def upgrade():
    # Manually create the index
    op.create_index("idx_events_timestamp", "events", ["timestamp"])
    op.execute(
        f"""
        CREATE SEQUENCE IF NOT EXISTS events_id_seq;
        ALTER TABLE events ALTER COLUMN id SET DEFAULT nextval('events_id_seq');
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {db_user};
        GRANT USAGE, SELECT ON SEQUENCE events_id_seq TO {db_user};
    """
    )


def downgrade():
    # Drop the index in case of rollback
    op.drop_index("idx_events_timestamp", table_name="events")
    op.execute(
        f"""
        REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM {db_user};
        REVOKE USAGE, SELECT ON SEQUENCE events_id_seq FROM {db_user};
        DROP SEQUENCE IF EXISTS events_id_seq;
    """
    )
