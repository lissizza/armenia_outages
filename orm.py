import asyncio
from datetime import datetime
import logging

from sqlalchemy.orm import Session as SQLAlchemySession
from db import session_scope
from models import Area, BotUser, Event, Language, Post

logger = logging.getLogger(__name__)


async def save_post_to_db(session, post_type, text, event_ids, language, area):
    """Save a generated post to the database with multiple event_ids asynchronously."""
    loop = asyncio.get_event_loop()
    events = await loop.run_in_executor(
        None, lambda: session.query(Event).filter(Event.id.in_(event_ids)).all()
    )

    post = Post(
        language=language,
        post_type=post_type,
        area=area,
        text=text,
        creation_time=datetime.now(),
        posted_time=None,
        events=events,
    )

    await loop.run_in_executor(None, session.add, post)
    logger.debug(f"Post saved to the database: {text[:60]}...")


async def clean_area_name(raw_name):
    prefixes = [
        "г.",
        "город",
        "с.",
        "деревня",
        "пгт",
        "поселок",
        "Ք.",
        "Քաղաք",
        "Գ.",
        "Գյուղ",
        "Վ.",
        "С.",
        "Г.",
        "V.",
        "V",
        "Ս.",
    ]

    for prefix in prefixes:
        if raw_name.startswith(prefix):
            raw_name = raw_name[len(prefix) :].strip()
            break
        elif "." in raw_name:
            raw_name = raw_name.split(".")[1].strip()
            break

    cleaned_name = raw_name.split("(")[0].strip()

    return cleaned_name.capitalize()


async def get_or_create_area(
    session: SQLAlchemySession, area_name: str, language: Language
) -> Area:
    """
    Retrieves an existing Area by name and language, or creates it if it doesn't exist.

    :param session: SQLAlchemy session.
    :param area_name: The name of the area.
    :param language: The language of the area.
    :return: The Area instance.
    """
    area_name = await clean_area_name(area_name)
    loop = asyncio.get_event_loop()

    # Check if the area already exists
    area = await loop.run_in_executor(
        None,
        lambda: session.query(Area)
        .filter_by(name=area_name, language=language)
        .first(),
    )

    # If the area doesn't exist, create it
    if not area:
        area = Area(name=area_name, language=language)
        session.add(area)
        await loop.run_in_executor(None, session.commit)

    return area


async def get_or_create_user(telegram_user, language=Language.EN, session=None):
    """
    Fetches the user from the database by Telegram user ID.
    If the user does not exist, it creates and saves the user in the database.

    :param telegram_id: Telegram user ID (update.effective_user.id)
    :param telegram_user: Telegram user object (update.effective_user), required if the user does not exist
    :param language: A Language enum representing the user's language. Defaults to 'EN'.
    :return: BotUser instance
    """
    with session_scope(session) as session:
        user = session.query(BotUser).filter_by(user_id=telegram_user.id).first()

        if not user:
            user = BotUser(
                user_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                language=language,
                date_joined=datetime.now(),
            )
            session.add(user)
            session.commit()
            logger.info(f"New user created: {user}")
        else:
            logger.info(f"User found: {user} with language: {user.language}")

        return user


async def update_or_create_user(
    telegram_user, language=Language.EN, session=None
) -> BotUser:
    """
    Updates an existing user or creates a new one in the database based on the provided Telegram user object.

    :param telegram_user: Telegram user object.
    :param language: Language preference for the user, defaults to 'EN'.
    :return: BotUser instance.
    """
    with session_scope(session) as session:
        user = session.query(BotUser).filter_by(user_id=telegram_user.id).first()

        if user:
            user.username = telegram_user.username
            user.first_name = telegram_user.first_name
            user.last_name = telegram_user.last_name
            user.language = language
            logger.info(f"User {telegram_user.id} found. Updating user information.")
        else:
            user = BotUser(
                user_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                language=language,
                date_joined=datetime.now(),
            )
            session.add(user)
            logger.info(
                f"No user found with telegram_id {telegram_user.id}. Creating new user."
            )

        return user
