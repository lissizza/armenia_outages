import logging
import re
import uuid
import jellyfish
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
from action_handlers.handlers import safe_reply_text
from db import session_scope
from models import BotUser, Subscription, Area, Language
from user_logic import get_or_create_user
from utils import get_translation
from handle_posts import get_or_create_area
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# Initialize translation system
translations = get_translation()

# Constants to define the state of the conversation
ASKING_FOR_KEYWORD, ASKING_FOR_AREA, VALIDATING_AREA = range(3)


async def subscribe(update: Update, context: CallbackContext) -> int:
    with session_scope() as session:
        user = await get_or_create_user(update.effective_user, session=session)
        user = session.merge(user)
        _ = translations[user.language.name]

        logger.info(f"User {user.username} issued /subscribe command")
        areas = (
            session.query(Area)
            .filter_by(language=user.language)
            .order_by(Area.name)
            .all()
        )

        if not areas:
            logger.warning("No areas found in the database.")
        else:
            logger.info(f"Found {len(areas)} areas.")

        keyboard = [
            [InlineKeyboardButton(area.name, callback_data=str(area.id))]
            for area in areas
        ]
        keyboard.append(
            [InlineKeyboardButton(_("Enter a new area"), callback_data="new")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            _("Please select an area from the list or enter a new one:"),
            reply_markup=reply_markup,
        )

    return ASKING_FOR_AREA


async def ask_new_area(update: Update, context: CallbackContext) -> int:
    user = await get_or_create_user(update.effective_user)
    _ = translations[user.language.name]

    await safe_reply_text(
        update, _("Please enter the name of the new area (letters only):")
    )
    return VALIDATING_AREA


async def handle_area(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text.strip()

    with session_scope() as session:
        user = await get_or_create_user(update.effective_user, session=session)
        user = session.merge(user)
        _ = translations[user.language.name]

        if not re.match(r"^[a-zA-Zа-яА-ЯёЁ\s]+$", user_input):
            await safe_reply_text(
                update, _("The area name must contain only letters. Please try again:")
            )
            return VALIDATING_AREA

        new_area = await get_or_create_area(session, user_input, user.language)

        # Translate area name and save in other languages
        translator_ru = GoogleTranslator(source="auto", target="ru")
        area_name_ru = translator_ru.translate(new_area.name)
        await get_or_create_area(session, area_name_ru, Language.RU)

        translator_hy = GoogleTranslator(source="auto", target="hy")
        area_name_hy = translator_hy.translate(new_area.name)
        await get_or_create_area(session, area_name_hy, Language.HY)

        context.user_data["selected_area"] = new_area.id
        await safe_reply_text(
            update,
            _("The area '{}' has been added and selected.").format(new_area.name),
        )

    return await ask_for_keyword(update, context)


async def select_area(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    with session_scope() as session:
        user = await get_or_create_user(query.from_user, session=session)
        _ = translations[user.language.name]

        area_id = int(query.data)
        area = session.query(Area).filter_by(id=area_id).first()

        if area:
            context.user_data["selected_area"] = area.id
            # await safe_reply_text(
            #     update, _("You selected the area: {}").format(area.name)
            # )
            return await ask_for_keyword(update, context, session)

        if query.data == "new":
            return await ask_new_area(update, context)

        await safe_reply_text(update, _("Area not found. Please try again."))
        return ASKING_FOR_AREA


async def ask_for_keyword(update: Update, context: CallbackContext, session) -> int:
    """
    Asks the user to provide a keyword to subscribe to.
    Handles both callback queries and regular messages.
    """
    user = await get_or_create_user(update.effective_user, session=session)
    _ = translations[user.language.name]

    request_message = _(
        "Please provide a keyword in your selected language ({}) to subscribe to:"
    ).format(user.language.name.upper())

    if update.message:
        await update.message.reply_text(request_message)
    elif update.callback_query:
        await update.callback_query.edit_message_text(request_message)
        await update.callback_query.answer()

    return ASKING_FOR_KEYWORD


async def handle_keyword(update: Update, context: CallbackContext) -> int:
    keyword = update.message.text.strip()

    with session_scope() as session:
        user = await get_or_create_user(update.effective_user, session=session)
        user = session.merge(user)
        _ = translations[user.language.name]

        # Validate the keyword
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

        await save_subscription(user, keyword, area_id, update, session)

    return ConversationHandler.END


async def save_subscription(
    user: BotUser, keyword: str, area_id: int, update: Update, session
) -> None:
    """
    Saves the subscription to the database.
    """
    _ = translations[user.language.name]

    try:
        logger.info(f"Saving subscription for user {user.user_id}")

        existing_subscription = (
            session.query(Subscription)
            .filter_by(user_id=user.user_id, area_id=area_id, keyword=keyword)
            .first()
        )

        if existing_subscription:
            logger.warning(
                f"Duplicate subscription attempt: {user.user_id} -> {keyword}"
            )
            await safe_reply_text(
                update,
                _(
                    "You are already subscribed to {}, {}. Please choose a different area or keyword."
                ).format(existing_subscription.area.name, keyword),
            )
            return

        subscription = Subscription(
            user_id=user.user_id, keyword=keyword, area_id=area_id
        )
        session.add(subscription)
        session.commit()

        logger.info(f"Subscription saved: {user.user_id} -> {keyword}")
        await safe_reply_text(
            update,
            _("You have successfully subscribed to {}, {}.").format(
                subscription.area.name, keyword
            ),
        )
    except Exception as e:
        logger.error(f"Failed to save subscription: {e}")
        await safe_reply_text(
            update,
            _(
                "An error occurred while trying to save the subscription. Please try again later."
            ),
        )


async def cancel(update: Update, context: CallbackContext) -> int:
    user = await get_or_create_user(update.effective_user)
    _ = translations[user.language.name]

    await safe_reply_text(update, _("Subscription cancelled."))
    return ConversationHandler.END


async def inline_query(update: Update, context: CallbackContext):
    query = update.inline_query.query
    if not query:
        return

    with session_scope() as session:
        user = await get_or_create_user(update.inline_query.from_user, session=session)
        user = session.merge(user)
        _ = translations[user.language.name]

        areas = session.query(Area).filter_by(language=user.language).all()

        area_scores = [
            (area, jellyfish.jaro_winkler(query.lower(), area.name.lower()))
            for area in areas
        ]

        matching_areas = sorted(area_scores, key=lambda x: x[1], reverse=True)

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


async def subscription_list(update: Update, context: CallbackContext) -> None:
    with session_scope() as session:
        user = await get_or_create_user(update.effective_user, session=session)
        user = session.merge(user)

        if user is None:
            await update.message.reply_text(
                "You are not registered. Please use the /start command to register."
            )
            return

        _ = translations[user.language.name]

        subscriptions = (
            session.query(Subscription).filter_by(user_id=user.user_id).all()
        )

        if subscriptions:
            for sub in subscriptions:
                text = f"{sub.area.name}, {sub.keyword}"
                button = InlineKeyboardButton(
                    "❌", callback_data=f"unsubscribe_{sub.id}"
                )
                markup = InlineKeyboardMarkup([[button]])
                await safe_reply_text(update, text, reply_markup=markup)

            response_text = _("Your subscriptions:")
        else:
            response_text = _("You have no subscriptions.")

        if not subscriptions:
            await safe_reply_text(update, response_text)


async def unsubscribe_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    with session_scope() as session:
        user = await get_or_create_user(query.from_user, session=session)
        user = session.merge(user)
        _ = translations[user.language.name]

        subscription_id = int(query.data.split("_")[1])
        subscription = session.query(Subscription).filter_by(id=subscription_id).first()

        if subscription:
            area_name = subscription.area.name
            keyword = subscription.keyword
            session.delete(subscription)
            session.commit()
            await query.edit_message_text(
                text=_("You have unsubscribed from {}, {}.").format(area_name, keyword)
            )
        else:
            await query.edit_message_text(
                text=_("Subscription not found or already removed.")
            )
