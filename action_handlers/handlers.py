import asyncio
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden
from telegram.ext import CallbackContext
from db import Session
from models import Subscription, Language
from user_logic import save_user, get_user_by_telegram_id
from utils import get_translation

logger = logging.getLogger(__name__)


# Initialize translations
locales_dir = os.path.join(os.path.dirname(__file__), "locales")
translations = get_translation()


async def error_handler(update: Update, context: CallbackContext) -> None:
    try:
        raise context.error
    except Forbidden:
        logging.warning(f"Bot was blocked by user {update.effective_user.id}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")


async def safe_reply_text(update: Update, text: str, **kwargs) -> None:
    try:
        await update.message.reply_text(text, **kwargs)
    except Forbidden:
        logging.warning(f"Bot was blocked by user {update.effective_user.id}")


async def start(update: Update, context: CallbackContext) -> None:
    telegram_id = update.effective_user.id
    user = await get_user_by_telegram_id(telegram_id)

    if user is None:
        await save_user(update.effective_user)
        user = await get_user_by_telegram_id(telegram_id)

    _ = translations[user.language.name]

    await update.message.reply_text(
        _(
            "Hello {}! I am a bot that tracks water and power outages. Choose your language:"
        ).format(user.first_name),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("English", callback_data="set_language EN")],
                [InlineKeyboardButton("Русский", callback_data="set_language RU")],
                [InlineKeyboardButton("Հայերեն", callback_data="set_language HY")],
            ]
        ),
    )


async def update_user_language(telegram_id: int, language: Language) -> None:
    """
    Asynchronously updates the language of the user in the database.

    :param telegram_id: Telegram user ID
    :param language: New language to be set
    """
    session = Session()
    try:
        user = await get_user_by_telegram_id(telegram_id)
        if user:
            logger.info(f"Current language for user {telegram_id}: {user.language}")
            user.language = language

            merged_user = session.merge(user)

            await asyncio.get_event_loop().run_in_executor(None, session.commit)
            logger.info(
                f"Commit successful for user {telegram_id}. Language should now be: {merged_user.language}"
            )
            session.refresh(merged_user)
            logger.info(
                f"After commit, language for user {telegram_id} is: {merged_user.language}"
            )
        else:
            logger.error(f"User with telegram_id {telegram_id} not found.")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update language for user {telegram_id}: {e}")
    finally:
        session.close()


async def set_language(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    telegram_id = query.from_user.id
    language_code = query.data.split()[-1]

    try:
        language = Language.from_code(language_code)
        logger.info(f"Setting language for user {telegram_id} to {language}")
        await update_user_language(telegram_id, language)

        user = await get_user_by_telegram_id(telegram_id)
        _ = translations[user.language.name]

        await query.answer(_("Language has been set to {}").format(language_code))
        await query.edit_message_text(
            _("Language has been set to {}").format(language_code)
        )
    except ValueError as e:
        logger.error(e)
        user = await get_user_by_telegram_id(telegram_id)
        _ = translations[user.language.name]

        await query.answer(_("Invalid language code"))


async def unsubscribe(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = await get_user_by_telegram_id(user_id)
    _ = translations[user.language.name]

    if len(context.args) < 1:
        await safe_reply_text(_("Usage: /unsubscribe <keyword>"))
        return

    keyword = context.args[0]

    session = Session()
    existing_subscription = (
        session.query(Subscription).filter_by(user_id=user_id, keyword=keyword).first()
    )

    if existing_subscription:
        session.delete(existing_subscription)
        session.commit()
        await safe_reply_text(
            _('You have unsubscribed from notifications for the keyword "{}".').format(
                keyword
            )
        )
    else:
        await safe_reply_text(
            _('You are not subscribed to notifications for the keyword "{}".').format(
                keyword
            )
        )

    session.close()


async def list_subscriptions(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = get_user_by_telegram_id(user_id)
    _ = translations[user.language.name]

    session = Session()
    subscriptions = session.query(Subscription).filter_by(user_id=user_id).all()
    if subscriptions:
        subscription_list = "\n".join(
            [f"{sub.keyword} ({sub.language})" for sub in subscriptions]
        )
        await safe_reply_text(
            update, _("Your subscriptions:\n{}").format(subscription_list)
        )
    else:
        await safe_reply_text(update, _("You have no subscriptions."))

    session.close()
