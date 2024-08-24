from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c67b9c04ebcd"
down_revision = "b2351782c401"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("areas", schema=None) as batch_op:

        batch_op.drop_constraint("uq_area_name_language", type_="unique")

        batch_op.create_unique_constraint("uq_area_name_language", ["name", "language"])

    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column("keyword", existing_type=sa.VARCHAR(), nullable=False)
        batch_op.alter_column("area_id", existing_type=sa.INTEGER(), nullable=False)
        batch_op.drop_constraint("fk_user_subscription", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_user_subscription", "bot_users", ["user_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_user_subscription", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_user_subscription", "bot_users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.alter_column("area_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column("keyword", existing_type=sa.VARCHAR(), nullable=True)
        batch_op.alter_column("user_id", existing_type=sa.INTEGER(), nullable=False)

    with op.batch_alter_table("areas", schema=None) as batch_op:
        batch_op.drop_constraint("uq_area_name_language", type_="unique")
        batch_op.create_unique_constraint("uq_area_name_language", ["name", "language"])
