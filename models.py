from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
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

    @property
    def text(self):
        return self.value[0]


class PostType(PyEnum):
    EMERGENCY_POWER = "emergency_power"
    EMERGENCY_WATER = "emergency_water"
    EMERGENCY_GAS = "emergency_gas"
    SCHEDULED_POWER = "scheduled_power"
    SCHEDULED_WATER = "scheduled_water"
    SCHEDULED_GAS = "scheduled_gas"


post_event_association = Table(
    "post_event_association",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("event_id", ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
)


class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    language = Column(Enum(Language), nullable=False)

    subscriptions = relationship("Subscription", back_populates="area")
    posts = relationship("Post", back_populates="area")

    __table_args__ = (
        UniqueConstraint("name", "language", name="uq_area_name_language"),
    )


class BotUser(Base):
    __tablename__ = "bot_users"

    user_id = Column(BigInteger, primary_key=True, unique=True, nullable=False)
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

    __table_args__ = (
        UniqueConstraint("hash", name="_event_hash_uc"),
        Index("idx_events_timestamp", "timestamp"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("bot_users.user_id"))
    keyword = Column(String, nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)
    created = Column(DateTime, default=datetime.now)

    user = relationship("BotUser", back_populates="subscriptions")
    area = relationship("Area", back_populates="subscriptions")
    notifications = relationship("Notification", back_populates="subscription")

    __table_args__ = (
        UniqueConstraint("user_id", "area_id", "keyword", name="_user_area_keyword_uc"),
    )


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    language = Column(Enum(Language), nullable=False)
    post_type = Column(Enum(PostType), nullable=False)
    text = Column(String, nullable=False)
    creation_time = Column(DateTime, default=datetime.now)
    posted_time = Column(DateTime, nullable=True)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)

    events = relationship(
        "Event",
        secondary=post_event_association,
        back_populates="posts",
        cascade="all, delete",
    )
    area = relationship("Area", back_populates="posts")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    language = Column(Enum(Language), nullable=False)
    notification_type = Column(Enum(PostType), nullable=False)
    text = Column(String, nullable=False)
    creation_time = Column(DateTime, default=datetime.now)
    sent_time = Column(DateTime, nullable=True)

    subscription = relationship("Subscription", back_populates="notifications")
