import asyncio
from datetime import datetime
import logging
from db import Session
from models import BotUser, Language

logger = logging.getLogger(__name__)


async def save_user(user, language=Language.EN) -> None:
    """
    Asynchronously saves a new user or updates an existing user in the database.

    :param user: Telegram user object (update.message.from_user)
    :param language: A string representing the language chosen by the user, defaults to 'en'
    """
    session = Session()

    existing_user = await asyncio.get_event_loop().run_in_executor(
        None, session.query(BotUser).filter_by(user_id=user.id).first
    )

    if not existing_user:
        # Create a new user
        new_user = BotUser(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=language,
            date_joined=datetime.now(),
        )
        session.add(new_user)
    else:
        # Update existing user's information
        existing_user.username = user.username
        existing_user.first_name = user.first_name
        existing_user.last_name = user.last_name
        existing_user.language = language

    await asyncio.get_event_loop().run_in_executor(None, session.commit)
    session.close()


async def get_user_by_telegram_id(telegram_id):
    """
    Fetches the user from the database by Telegram user ID.

    :param telegram_id: Telegram user ID (update.effective_user.id)
    :return: BotUser instance or None if not found
    """
    loop = asyncio.get_event_loop()
    session = Session()
    user = await loop.run_in_executor(
        None, lambda: session.query(BotUser).filter_by(user_id=telegram_id).first()
    )

    if user:
        logger.info(f"User found: {user} with language: {user.language}")
    else:
        logger.error(f"No user found with telegram_id {telegram_id}")

    session.close()
    return user
