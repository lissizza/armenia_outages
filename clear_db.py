from db import Session
from models import Event, ProcessedEvent, LastPage


def clear_database():
    session = Session()
    session.query(Event).delete()
    session.query(ProcessedEvent).delete()
    session.query(LastPage).delete()
    session.commit()
    session.close()


if __name__ == "__main__":
    clear_database()
    print("Database cleared.")
