from datetime import datetime
from db import Session
from models import BotUser, Language


def save_user(user, language=Language.EN) -> None:
    """
    Saves a new user or updates an existing user in the database.

    :param user: Telegram user object (update.message.from_user)
    :param language: A string representing the language chosen by the user, defaults to 'en'
    """
    session = Session()

    existing_user = session.query(BotUser).filter_by(user_id=user.id).first()

    if not existing_user:
        # Create a new user
        new_user = BotUser(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=language,
            date_joined=datetime.utcnow(),
        )
        session.add(new_user)
        session.commit()
    else:
        # Update existing user's information
        existing_user.username = user.username
        existing_user.first_name = user.first_name
        existing_user.last_name = user.last_name
        existing_user.language = language
        session.commit()
