"""rename sent field to processed in events table

Revision ID: ba04c31a1fa1
Revises: 44f7699e3008
Create Date: 2024-08-10 15:10:42.079120

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ba04c31a1fa1"
down_revision: Union[str, None] = "44f7699e3008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Renaming the column sent to processed
    op.alter_column("events", "sent", new_column_name="processed")


def downgrade():
    # Rename processed back to sent in case of a downgrade
    op.alter_column("events", "processed", new_column_name="sent")
