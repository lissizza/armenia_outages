from datetime import datetime
import logging
from db import session_scope
from models import BotUser, Language

logger = logging.getLogger(__name__)


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
