import logging
import re
from sqlite3 import IntegrityError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from db import Session
from models import BotUser, Subscription, Area, Language
from user_logic import get_user_by_telegram_id
from utils import get_translation
from handle_posts import clean_area_name
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# Initialize translation system
translations = get_translation()

# Constants to define the state of the conversation
ASKING_FOR_KEYWORD, ASKING_FOR_AREA, VALIDATING_AREA = range(3)


async def subscribe(update: Update, context: CallbackContext) -> int:
    """
    Entry point for the /subscribe command.
    Prompts the user to select or enter an area.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    session = Session()
    areas = session.query(Area).filter_by(language=user.language).all()

    keyboard = [
        [InlineKeyboardButton(area.name, callback_data=str(area.id))] for area in areas
    ]
    keyboard.append([InlineKeyboardButton(_("Enter a new area"), callback_data="new")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        _("Please select an area from the list or enter a new one:"),
        reply_markup=reply_markup,
    )

    session.close()
    return ASKING_FOR_AREA


async def ask_new_area(update: Update, context: CallbackContext) -> int:
    """
    Asks the user to enter a new area name.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    await update.message.reply_text(
        _("Please enter the name of the new area (letters only):")
    )
    return VALIDATING_AREA


async def validate_area(update: Update, context: CallbackContext) -> int:
    """
    Validates the area name entered by the user, ensuring it contains only letters.
    Adds the area to the database if it's valid.
    """
    user_input = update.message.text
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    # Validate that the input contains only letters
    if not re.match(r"^[a-zA-Zа-яА-ЯёЁ\s]+$", user_input):
        await update.message.reply_text(
            _("The area name must contain only letters. Please try again:")
        )
        return VALIDATING_AREA

    area_name = clean_area_name(user_input)

    # Translate to other languages
    translator = GoogleTranslator(source="auto", target="ru")
    area_name_ru = translator.translate(area_name)

    translator = GoogleTranslator(source="auto", target="hy")
    area_name_hy = translator.translate(area_name)

    session = Session()

    # Add the new area
    new_area = Area(name=area_name, language=user.language)
    session.add(new_area)
    session.commit()

    # Add translations to the database
    session.add(Area(name=area_name_ru, language=Language.RU))
    session.add(Area(name=area_name_hy, language=Language.HY))
    session.commit()

    context.user_data["selected_area"] = new_area.id
    await update.message.reply_text(
        _("The area '{}' has been added and selected.").format(area_name)
    )

    session.close()

    return await ask_for_keyword(update, context)


async def select_area(update: Update, context: CallbackContext) -> int:
    """
    Handles the selection of an area from the list or prompts the user to enter a new one.
    """
    query = update.callback_query
    await query.answer()

    user = await get_user_by_telegram_id(query.from_user.id)
    _ = translations[user.language.name]

    if query.data == "new":
        return await ask_new_area(update, context)

    area_id = int(query.data)
    context.user_data["selected_area"] = area_id
    await query.edit_message_text(
        text=_("You selected area with ID: {}").format(area_id)
    )

    return await ask_for_keyword(update, context)


async def ask_for_keyword(update: Update, context: CallbackContext) -> int:
    """
    Asks the user to provide a keyword to subscribe to.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    await update.message.reply_text(_("Please provide a keyword to subscribe to:"))
    return ASKING_FOR_KEYWORD


async def handle_keyword(update: Update, context: CallbackContext) -> int:
    """
    Handles the keyword provided by the user and saves the subscription.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]
    keyword = update.message.text

    area_id = context.user_data.get("selected_area")
    if not area_id:
        await update.message.reply_text(_("Please select an area first."))
        return ConversationHandler.END

    await save_subscription(user, keyword, area_id)
    await update.message.reply_text(_("You have subscribed to {}.").format(keyword))
    return ConversationHandler.END


async def save_subscription(user: BotUser, keyword: str, area_id: int):
    """
    Saves the subscription to the database.
    """
    session = Session()
    subscription = Subscription(user_id=user.user_id, keyword=keyword, area_id=area_id)

    try:
        session.add(subscription)
        session.commit()
        logger.info(f"Subscription saved: {user.user_id} -> {keyword}")
    except IntegrityError as e:
        session.rollback()
        logger.error(f"Failed to save subscription: {e}")
    finally:
        session.close()


async def cancel(update: Update, context: CallbackContext) -> int:
    """
    Cancels the subscription process if the user decides not to continue.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    await update.message.reply_text(_("Subscription cancelled."))
    return ConversationHandler.END


# ConversationHandler for the /subscribe command
subscribe_handler = ConversationHandler(
    entry_points=[CommandHandler("subscribe", subscribe)],
    states={
        ASKING_FOR_AREA: [CallbackQueryHandler(select_area)],
        VALIDATING_AREA: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, validate_area)
        ],
        ASKING_FOR_KEYWORD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyword)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
