from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ffc18e1a5dd6"
down_revision: str = "e754d72da764"
branch_labels: None
depends_on: None


def upgrade():

    post_type_enum = sa.Enum(
        "EMERGENCY_POWER",
        "EMERGENCY_WATER",
        "EMERGENCY_GAS",
        "SCHEDULED_POWER",
        "SCHEDULED_WATER",
        "SCHEDULED_GAS",
        name="posttype",
    )
    post_type_enum.create(op.get_bind())  # Создание ENUM типа в базе данных

    op.add_column("posts", sa.Column("post_type", post_type_enum, nullable=True))


def downgrade():

    op.drop_column("posts", "post_type")

    post_type_enum = sa.Enum(
        "EMERGENCY_POWER",
        "EMERGENCY_WATER",
        "EMERGENCY_GAS",
        "SCHEDULED_POWER",
        "SCHEDULED_WATER",
        "SCHEDULED_GAS",
        name="posttype",
    )
    post_type_enum.drop(op.get_bind())
