from sqlalchemy import Column, Integer, String, Enum, UniqueConstraint, Boolean, Text
from db import Base
from enum import Enum as PyEnum


class EventType(PyEnum):
    POWER = "power"
    WATER = "water"
    GAS = "gas"


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
    language = Column(Enum(Language))

    area = Column(String)
    district = Column(String)
    house_number = Column(String)
    start_time = Column(String)
    end_time = Column(String)
    text = Column(Text)
    planned = Column(Boolean)

    processed = Column(Boolean, default=False)
    timestamp = Column(String)
    hash = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint("hash", name="_event_hash_uc"),)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    keyword = Column(String)
    language = Column(Enum(Language))


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(Enum(EventType), nullable=False)
    language = Column(Enum(Language), nullable=False)

    area = Column(String, nullable=True)
    district = Column(String, nullable=True)
    house_numbers = Column(Text, nullable=True)
    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)
    text = Column(Text, nullable=True)
    planned = Column(Boolean)

    timestamp = Column(String)
    sent = Column(Boolean, default=False)
    sent_time = Column(String)

    __table_args__ = (
        UniqueConstraint(
            "start_time", "area", "district", "language", name="_unique_agg_event"
        ),
    )
