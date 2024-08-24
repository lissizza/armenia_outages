import logging
from sqlite3 import IntegrityError
from telegram import Update
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from db import Session
from models import BotUser, Subscription
from user_logic import get_user_by_telegram_id
from utils import get_translation

logger = logging.getLogger(__name__)

# Initialize translation system
translations = get_translation()

# Constants to define the state of the conversation
ASKING_FOR_KEYWORD = 1


async def subscribe(update: Update, context: CallbackContext) -> int:
    """
    Handles the /subscribe command. If an argument is provided, subscribes to that keyword.
    If no argument is provided, prompts the user to enter a keyword.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]

    if context.args:
        keyword = context.args[0]
        await save_subscription(user, keyword)
        await update.message.reply_text(_("You have subscribed to {}.").format(keyword))
        return ConversationHandler.END
    else:
        await update.message.reply_text(_("Please provide a keyword to subscribe to:"))
        return ASKING_FOR_KEYWORD


async def handle_keyword(update: Update, context: CallbackContext) -> int:
    """
    Handles the user's response when they provide a keyword after being prompted.
    """
    user = await get_user_by_telegram_id(update.effective_user.id)
    _ = translations[user.language.name]
    keyword = update.message.text
    await save_subscription(user, keyword)
    await update.message.reply_text(_("You have subscribed to {}.").format(keyword))
    return ConversationHandler.END


async def save_subscription(user: BotUser, keyword: str):
    """
    Saves the subscription to the database.
    """
    session = Session()
    subscription = Subscription(user_id=user.user_id, keyword=keyword)

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
    _ = translations[user.language.name]  # Get the appropriate translation function

    await update.message.reply_text(_("Subscription cancelled."))
    return ConversationHandler.END


# Setting up the conversation handler for the /subscribe command
subscribe_handler = ConversationHandler(
    entry_points=[CommandHandler("subscribe", subscribe)],
    states={
        ASKING_FOR_KEYWORD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyword)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
