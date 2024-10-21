from contextlib import asynccontextmanager
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DB_URI

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO
)

engine = create_async_engine(
    DB_URI,
    echo=False,
    pool_pre_ping=True,
    connect_args={"options": "-c statement_timeout=60000"},
)
async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope(session=None):
    """Provide a transactional scope around a series of operations."""
    if session is None:
        session = async_session()
        is_new_session = True
    else:
        is_new_session = False

    try:
        yield session
        if is_new_session:
            await session.commit()
    except Exception:
        if is_new_session:
            await session.rollback()
        raise
    finally:
        if is_new_session:
            await session.close()
