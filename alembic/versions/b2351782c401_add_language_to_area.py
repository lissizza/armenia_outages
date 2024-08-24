"""Add language to Area

Revision ID: b2351782c401
Revises: 8e06aeb41865
Create Date: 2024-08-24 14:57:43.985427

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2351782c401"
down_revision: Union[str, None] = "8e06aeb41865"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the language column to the areas table
    with op.batch_alter_table("areas", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "language", sa.Enum("HY", "RU", "EN", name="language"), nullable=False
            )
        )
        batch_op.drop_constraint("uq_area_name", type_="unique")
        batch_op.create_unique_constraint("uq_area_name_language", ["name", "language"])


def downgrade() -> None:
    # Drop the language column from the areas table
    with op.batch_alter_table("areas", schema=None) as batch_op:
        batch_op.drop_constraint("uq_area_name_language", type_="unique")
        batch_op.create_unique_constraint("uq_area_name", ["name"])
        batch_op.drop_column("language")
