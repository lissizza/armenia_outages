from datetime import datetime
import logging

from sqlalchemy.future import select
from db import session_scope
from models import Area, BotUser, Event, Language, Post

logger = logging.getLogger(__name__)


async def save_post_to_db(session, post_type, text, event_ids, language, area):
    """Save a generated post to the database with multiple event_ids asynchronously."""
    events = await session.execute(select(Event).filter(Event.id.in_(event_ids)))
    events = events.scalars().all()

    post = Post(
        language=language,
        post_type=post_type,
        area=area,
        text=text,
        creation_time=datetime.now(),
        posted_time=None,
        events=events,
    )

    session.add(post)
    await session.commit()
    logger.debug(f"Post saved to the database: {text[:60]}...")


async def clean_area_name(raw_name):
    """
    Cleans the area name by removing common prefixes and trimming extra spaces.
    """
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

    # Check and remove prefixes
    for prefix in prefixes:
        if raw_name.startswith(prefix):
            raw_name = raw_name[len(prefix) :].strip()
            break
        elif "." in raw_name:
            raw_name = raw_name.split(".")[1].strip()
            break

    # Remove any extra parts in parentheses and capitalize the result
    cleaned_name = raw_name.split("(")[0].strip()

    return cleaned_name.capitalize() if cleaned_name else ""


async def get_or_create_area(session, area_name: str, language: Language) -> Area:
    """
    Retrieves an existing Area by name and language, or creates it if it doesn't exist.
    """
    # Clean the area name
    area_name = await clean_area_name(area_name)

    # Skip or handle empty area names
    if not area_name:
        logger.warning("Area name is empty after cleaning. Skipping area creation.")
        return None

    # Check if the area already exists
    result = await session.execute(
        select(Area).filter_by(name=area_name, language=language)
    )
    area = result.scalars().first()

    # If the area doesn't exist, create it
    if not area:
        area = Area(name=area_name, language=language)
        session.add(area)
        await session.commit()

    return area


async def get_or_create_user(
    telegram_user, language=Language.EN, session=None
) -> BotUser:
    """
    Fetches the user from the database by Telegram user ID.
    If the user does not exist, it creates and saves the user in the database.
    """
    async with session_scope(session) as session:
        result = await session.execute(
            select(BotUser).filter_by(user_id=telegram_user.id)
        )
        user = result.scalars().first()

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
            await session.commit()
            logger.info(f"New user created: {user}")
        else:
            logger.info(f"User found: {user} with language: {user.language}")

        return user


async def update_or_create_user(
    telegram_user, language=Language.EN, session=None
) -> BotUser:
    """
    Updates an existing user or creates a new one in the database based on the provided Telegram user object.
    """
    async with session_scope(session) as session:
        result = await session.execute(
            select(BotUser).filter_by(user_id=telegram_user.id)
        )
        user = result.scalars().first()

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

        await session.commit()
        return user
