"""remove id from botuser

Revision ID: b43c49dd73be
Revises: 378b2c70cc5f
Create Date: 2024-08-26 06:32:15.790741

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b43c49dd73be"
down_revision: Union[str, None] = "378b2c70cc5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Drop the old foreign key constraint
    op.drop_constraint(
        "subscriptions_user_id_fkey", "subscriptions", type_="foreignkey"
    )

    # Drop the old `id` column
    op.drop_column("bot_users", "id")

    # Create a new foreign key constraint using `user_id`
    op.create_foreign_key(
        "subscriptions_user_id_fkey",
        "subscriptions",
        "bot_users",
        ["user_id"],
        ["user_id"],
    )


def downgrade():
    # Reverse the above steps in case of downgrade
    op.drop_constraint(
        "subscriptions_user_id_fkey", "subscriptions", type_="foreignkey"
    )

    # Recreate the `id` column
    op.add_column(
        "bot_users", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True)
    )

    # Restore the original foreign key
    op.create_foreign_key(
        "subscriptions_user_id_fkey", "subscriptions", "bot_users", ["user_id"], ["id"]
    )
