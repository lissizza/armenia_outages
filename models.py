from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Enum,
    Table,
    UniqueConstraint,
    Boolean,
    Text,
)
from sqlalchemy.orm import relationship
from db import Base
from enum import Enum as PyEnum


class EventType(PyEnum):
    POWER = "power"
    WATER = "water"
    GAS = "gas"


class Language(PyEnum):
    RU = ("ru", 3)
    EN = ("en", 2)
    HY = ("hy", 1)

    @property
    def code(self):
        return self.value[1]


post_event_association = Table(
    "post_event_association",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id"), primary_key=True),
    Column("event_id", ForeignKey("events.id"), primary_key=True),
)


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

    posts = relationship(
        "Post", secondary=post_event_association, back_populates="events"
    )

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
            "start_time",
            "area",
            "district",
            "event_type",
            "language",
            name="_unique_agg_event",
        ),
    )


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    language = Column(String(2), nullable=False)
    text = Column(String, nullable=False)
    creation_time = Column(DateTime, nullable=False)
    posted_time = Column(DateTime, nullable=True)

    events = relationship(
        "Event", secondary=post_event_association, back_populates="posts"
    )
