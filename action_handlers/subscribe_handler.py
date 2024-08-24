import logging
import re
import uuid
import jellyfish
from sqlite3 import IntegrityError
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
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
from handle_posts import get_or_create_area
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# Initialize translation system
translations = get_translation()

# Constants to define the state of the conversation
ASKING_FOR_KEYWORD, ASKING_FOR_AREA, VALIDATING_AREA = range(3)


async def subscribe(update: Update, context: CallbackContext) -> int:
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    logger.info(f"User {user.username} issued /subscribe command")

    session = Session()
    areas = session.query(Area).filter_by(language=user.language).all()

    if not areas:
        logger.warning("No areas found in the database.")
    else:
        logger.info(f"Found {len(areas)} areas.")

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
    Handles both callback queries and regular messages.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    if update.message:
        await update.message.reply_text(
            _("Please enter the name of the new area (letters only):")
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            _("Please enter the name of the new area (letters only):")
        )
        await update.callback_query.answer()

    return VALIDATING_AREA


async def handle_area(update: Update, context: CallbackContext) -> int:
    """
    Validates the area name entered by the user, ensuring it contains only letters.
    Adds the area to the database if it's valid.
    """
    user_input = update.message.text.strip()
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    # Validate that the input contains only letters
    if not re.match(r"^[a-zA-Zа-яА-ЯёЁ\s]+$", user_input):
        await update.message.reply_text(
            _("The area name must contain only letters. Please try again:")
        )
        return VALIDATING_AREA

    session = Session()

    # Get or create the area in the user's language
    new_area = await get_or_create_area(session, user_input, user.language)

    # Translate the area name to other languages and ensure they exist in the database
    translator = GoogleTranslator(source="auto", target="ru")
    area_name_ru = translator.translate(new_area.name)
    await get_or_create_area(session, area_name_ru, Language.RU)

    translator = GoogleTranslator(source="auto", target="hy")
    area_name_hy = translator.translate(new_area.name)
    await get_or_create_area(session, area_name_hy, Language.HY)

    context.user_data["selected_area"] = new_area.id
    await update.message.reply_text(
        _("The area '{}' has been added and selected.").format(new_area.name)
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

    area_id = int(query.data)

    # Retrieve the selected area from the database
    session = Session()
    area = session.query(Area).filter_by(id=area_id).first()

    if area:
        context.user_data["selected_area"] = area.id
        await query.edit_message_text(
            text=_("You selected the area: {}").format(area.name)
        )
        session.close()
        return await ask_for_keyword(update, context)

    if query.data == "new":
        session.close()
        return await ask_new_area(update, context)

    session.close()
    await query.edit_message_text(text=_("Area not found. Please try again."))
    return ASKING_FOR_AREA


async def ask_for_keyword(update: Update, context: CallbackContext) -> int:
    """
    Asks the user to provide a keyword to subscribe to.
    Handles both callback queries and regular messages.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    if update.message:
        await update.message.reply_text(_("Please provide a keyword to subscribe to:"))
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            _("Please provide a keyword to subscribe to:")
        )
        await update.callback_query.answer()

    return ASKING_FOR_KEYWORD


async def handle_keyword(update: Update, context: CallbackContext) -> int:
    """
    Handles the keyword provided by the user and saves the subscription.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]
    keyword = update.message.text.strip()

    # Validate the keyword: only letters and digits, length >= 3
    if not re.match(r"^[a-zA-Zа-яА-ЯёЁ0-9\s]+$", keyword) or len(keyword) < 3:
        await update.message.reply_text(
            _(
                "The keyword must contain only letters, digits, and be at least 3 characters long. Please try again:"
            )
        )
        return ASKING_FOR_KEYWORD

    area_id = context.user_data.get("selected_area")
    if not area_id:
        await update.message.reply_text(_("Please select an area first."))
        return ConversationHandler.END

    session = Session()
    area = session.query(Area).filter_by(id=area_id).first()

    await save_subscription(user, keyword, area_id)
    await update.message.reply_text(
        _("You have subscribed to {}, {}.").format(area.name, keyword)
    )

    session.close()
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


async def inline_query(update: Update, context: CallbackContext):
    query = update.inline_query.query
    if not query:
        return

    user = await get_user_by_telegram_id(update.inline_query.from_user.id)
    _ = translations[user.language.name]

    session = Session()
    areas = session.query(Area).filter_by(language=user.language).all()

    # Calculate similarity scores using Jaro-Winkler distance
    area_scores = [
        (area, jellyfish.jaro_winkler(query.lower(), area.name.lower()))
        for area in areas
    ]

    # Sort areas by similarity score in descending order
    matching_areas = sorted(area_scores, key=lambda x: x[1], reverse=True)

    # Filter results with a minimum similarity threshold (e.g., 0.7)
    results = [
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=area.name,
            input_message_content=InputTextMessageContent(area.name),
        )
        for area, score in matching_areas
        if score > 0.7
    ]

    await update.inline_query.answer(results)


# ConversationHandler for the /subscribe command
subscribe_handler = ConversationHandler(
    entry_points=[CommandHandler("subscribe", subscribe)],
    states={
        ASKING_FOR_AREA: [CallbackQueryHandler(select_area)],
        VALIDATING_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_area)],
        ASKING_FOR_KEYWORD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyword)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
)
