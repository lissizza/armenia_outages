from alembic import op
import sqlalchemy as sa

# Migration identifiers
revision = "c8f7ceab9f3e"
down_revision = "6cbfba7bcbff"
branch_labels = None
depends_on = None


def upgrade():
    # Create areas table
    op.create_table(
        "areas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.UniqueConstraint("name", name="uq_area_name"),
    )

    # Add area_id to subscriptions table
    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("area_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_subscriptions_area", "areas", ["area_id"], ["id"]
        )

    # Add area_id to posts table
    with op.batch_alter_table("posts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("area_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_posts_area", "areas", ["area_id"], ["id"])


def downgrade():
    # Drop foreign key and column from posts table
    with op.batch_alter_table("posts", schema=None) as batch_op:
        batch_op.drop_constraint("fk_posts_area", type_="foreignkey")
        batch_op.drop_column("area_id")

    # Drop foreign key and column from subscriptions table
    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_subscriptions_area", type_="foreignkey")
        batch_op.drop_column("area_id")

    # Drop areas table
    op.drop_table("areas")
