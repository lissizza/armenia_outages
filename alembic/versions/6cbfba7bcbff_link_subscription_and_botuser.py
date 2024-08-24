"""link Subscription and BotUser

Revision ID: 6cbfba7bcbff
Revises: 9201c26ccb5d
Create Date: 2024-08-24 13:34:38.401343

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6cbfba7bcbff"
down_revision: Union[str, None] = "9201c26ccb5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.drop_column("user_id")

    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            constraint_name="fk_user_subscription",
            referent_table="bot_users",
            local_cols=["user_id"],
            remote_cols=["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_user_subscription", type_="foreignkey")
        batch_op.drop_column("user_id")

    # Re-add the old `user_id` column
    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
