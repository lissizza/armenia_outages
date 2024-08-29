from contextlib import contextmanager
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DB_URI

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO
)
# logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

engine = create_engine(
    DB_URI,
    echo=False,
    pool_pre_ping=True,
    connect_args={"options": "-c statement_timeout=60000"},
    future=True,
)
Session = sessionmaker(bind=engine)
Base = declarative_base()


def init_db():
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(session=None):
    if session is None:
        session = Session()
        is_new_session = True
    else:
        is_new_session = False

    try:
        yield session
        if is_new_session:
            session.commit()
    except Exception:
        if is_new_session:
            session.rollback()
        raise
    finally:
        if is_new_session:
            session.close()
