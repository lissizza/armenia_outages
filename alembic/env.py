from sqlalchemy import create_engine, pool
from alembic import context
from logging.config import fileConfig
from models import Base
import os

config = context.config
fileConfig(config.config_file_name)


def get_sync_db_url():
    return os.getenv("SYNC_DATABASE_URL")  # Fetch a sync db URL, i.e., with psycopg2


target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = get_sync_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migration()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = create_engine(get_sync_db_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
