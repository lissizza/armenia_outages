from sqlalchemy import Column, Integer, String, Enum
from db import Base
from enum import Enum as PyEnum


class EventType(PyEnum):
    ELECTRICITY = "electricity"
    WATER = "water"


class Language(PyEnum):
    EN = "en"
    RU = "ru"
    AM = "am"


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    event_type = Column(Enum(EventType))
    area = Column(String)
    city = Column(String)
    street = Column(String)
    house_numbers = Column(String)
    start_time = Column(String)
    end_time = Column(String)
    language = Column(Enum(Language))


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    keyword = Column(String, unique=True)
    language = Column(Enum(Language))
