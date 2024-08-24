from datetime import datetime
from sqlalchemy import (
    BigInteger,
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

    @classmethod
    def from_code(cls, code):
        for member in cls:
            if member.name == code:
                return member
        raise ValueError(f"'{code}' is not a valid Language")


post_event_association = Table(
    "post_event_association",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id"), primary_key=True),
    Column("event_id", ForeignKey("events.id"), primary_key=True),
)


class BotUser(Base):
    __tablename__ = "bot_users"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    date_joined = Column(DateTime, default=datetime.now)
    language = Column(Enum(Language), default=Language.EN)

    subscriptions = relationship("Subscription", back_populates="user")

    def __repr__(self):
        return f"<BotUser(user_id={self.user_id}, username={self.username}, language={self.language})>"


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
    timestamp = Column(DateTime, default=datetime.now())
    hash = Column(String, nullable=False)

    posts = relationship(
        "Post", secondary=post_event_association, back_populates="events"
    )

    __table_args__ = (UniqueConstraint("hash", name="_event_hash_uc"),)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("bot_users.id"))
    keyword = Column(String)
    created = Column(DateTime, default=datetime.now)

    user = relationship("BotUser", back_populates="subscriptions")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    language = Column(Enum(Language), nullable=False)
    text = Column(String, nullable=False)
    creation_time = Column(DateTime, default=datetime.now)
    posted_time = Column(DateTime, nullable=True)

    events = relationship(
        "Event", secondary=post_event_association, back_populates="posts"
    )
