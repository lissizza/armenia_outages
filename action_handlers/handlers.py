import os
import logging
from db import session_scope
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from telegram.error import Forbidden
from models import Language
from user_logic import (
    get_or_create_user,
    update_or_create_user,
)
from utils import get_translation

logger = logging.getLogger(__name__)


# Initialize translations
locales_dir = os.path.join(os.path.dirname(__file__), "locales")
translations = get_translation()


async def safe_reply_text(update: Update, text: str, **kwargs) -> None:
    try:
        if update.message:
            await update.message.reply_text(text, **kwargs)
        elif update.callback_query:
            await update.callback_query.message.reply_text(text, **kwargs)
            await update.callback_query.answer()
    except Forbidden:
        logging.warning(f"Bot was blocked by user {update.effective_user.id}")


async def start(update: Update, context: CallbackContext) -> None:
    with session_scope() as session:
        user = await get_or_create_user(update.effective_user, session=session)
        user = session.merge(user)
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


async def set_language(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    telegram_id = query.from_user.id
    language_code = query.data.split()[-1]

    try:
        language = Language.from_code(language_code)
        logger.info(f"Setting language for user {telegram_id} to {language}")
        
        with session_scope() as session:
            user = await update_or_create_user(query.from_user, language=language, session=session)
            user = session.merge(user)

            if user:
                _ = translations[user.language.name]
                await query.answer(_("Language has been set to {}").format(language_code))
                await query.edit_message_text(
                    _("Language has been set to {}").format(language_code)
                )
            else:
                logger.error(
                    f"User with telegram_id {telegram_id} could not be found or saved."
                )
                await query.answer(_("An error occurred. Please try again."))

    except ValueError as e:
        logger.error(e)
        with session_scope() as session:
            user = await get_or_create_user(query.from_user, session=session)
            user = session.merge(user)  # Привязываем объект user к текущей сессии

            if user:
                _ = translations[user.language.name]
                await query.answer(_("Invalid language code"))
            else:
                await query.answer(_("An error occurred. Please try again."))

