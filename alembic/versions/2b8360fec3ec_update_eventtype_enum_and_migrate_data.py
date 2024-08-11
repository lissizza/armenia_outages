"""Update EventType enum and migrate data

Revision ID: 2b8360fec3ec
Revises: 77365e983e7c
Create Date: 2024-08-09 17:49:54.808480

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b8360fec3ec"
down_revision: Union[str, None] = "77365e983e7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Step 1: Update all 'ELECTRICITY' values to 'POWER'
    op.execute(
        "UPDATE events SET event_type = 'POWER' WHERE event_type = 'ELECTRICITY'"
    )

    # Step 2: Recreate the enum with the new values and alter the column
    with op.batch_alter_table("events") as batch_op:
        batch_op.alter_column(
            "event_type",
            existing_type=sa.Enum("ELECTRICITY", "WATER", name="eventtype"),
            type_=sa.Enum("POWER", "WATER", "GAS", name="eventtype"),
            existing_nullable=False,
        )


def downgrade():
    # Step 1: Revert 'POWER' back to 'ELECTRICITY'
    op.execute(
        "UPDATE events SET event_type = 'ELECTRICITY' WHERE event_type = 'POWER'"
    )

    # Step 2: Recreate the old enum with the old values and alter the column
    with op.batch_alter_table("events") as batch_op:
        batch_op.alter_column(
            "event_type",
            existing_type=sa.Enum("POWER", "WATER", "GAS", name="eventtype"),
            type_=sa.Enum("ELECTRICITY", "WATER", name="eventtype"),
            existing_nullable=False,
        )
