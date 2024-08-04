from sqlalchemy import Column, Integer, String, Enum, UniqueConstraint, Boolean
from db import Base
from enum import Enum as PyEnum


class EventType(PyEnum):
    ELECTRICITY = "electricity"
    WATER = "water"


class Language(PyEnum):
    RU = ("ru", 3)
    EN = ("en", 2)
    AM = ("am", 1)

    @property
    def code(self):
        return self.value[1]


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    event_type = Column(Enum(EventType))
    area = Column(String)
    district = Column(String)
    house_number = Column(String)
    start_time = Column(String)
    end_time = Column(String)
    language = Column(Enum(Language))
    planned = Column(Integer)
    hash = Column(String, unique=True)
    timestamp = Column(String)
    sent = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("hash", name="_event_hash_uc"),)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    keyword = Column(String)
    language = Column(Enum(Language))


class LastPage(Base):
    __tablename__ = "last_page"
    id = Column(Integer, primary_key=True)
    page_number = Column(Integer)
    language = Column(Enum(Language))
    planned = Column(Integer)
