import os
import gettext
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from db import Session
from models import Subscription, Language

# Initialize translations
locales_dir = os.path.join(os.path.dirname(__file__), "locales")
translations = {}
for lang in [lang.value[0] for lang in Language]:
    try:
        translations[lang] = gettext.translation(
            "messages", localedir=locales_dir, languages=[lang], fallback=True
        )
    except Exception as e:
        logging.error(f"Error loading translation for {lang}: {e}")

user_languages = {}


async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_languages[user_id] = Language.EN.value[0]
    _ = translations[Language.EN.value[0]].gettext
    await update.message.reply_text(
        _(
            "Hello! I am a bot that tracks water and power outages. Choose your language:"
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("English", callback_data="set_language en")],
                [InlineKeyboardButton("Русский", callback_data="set_language ru")],
                [InlineKeyboardButton("Հայերեն", callback_data="set_language am")],
            ]
        ),
    )


async def set_language(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    language_code = query.data.split()[-1]

    if language_code not in [lang.value[0] for lang in Language]:
        _ = translations[user_languages.get(user_id, Language.EN.value[0])].gettext
        await query.answer(_("Invalid language choice."))
        return

    user_languages[user_id] = language_code
    _ = translations[user_languages[user_id]].gettext
    await query.answer(_("Language has been set to {}").format(language_code))
    await query.edit_message_text(
        _("Language has been set to {}").format(language_code)
    )


async def subscribe(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_language = user_languages.get(user_id, Language.EN.value[0])
    _ = translations[user_language].gettext

    if len(context.args) < 1:
        await update.message.reply_text(_("Usage: /subscribe <keyword>"))
        return

    keyword = context.args[0]

    if not (3 <= len(keyword) <= 256):
        await update.message.reply_text(
            _("Keyword must be between 3 and 256 characters long.")
        )
        return

    session = Session()
    existing_subscription = (
        session.query(Subscription).filter_by(user_id=user_id, keyword=keyword).first()
    )

    if existing_subscription:
        await update.message.reply_text(
            _(
                'Subscription for keyword "{}" already exists. Please choose another keyword.'
            ).format(keyword)
        )
    else:
        subscription = Subscription(
            user_id=user_id,
            keyword=keyword,
            language=user_language,
        )
        session.add(subscription)
        session.commit()
        await update.message.reply_text(
            _('You have subscribed to notifications for the keyword "{}".').format(
                keyword
            )
        )

    session.close()


async def unsubscribe(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_language = user_languages.get(user_id, Language.EN.value[0])
    _ = translations[user_language].gettext

    if len(context.args) < 1:
        await update.message.reply_text(_("Usage: /unsubscribe <keyword>"))
        return

    keyword = context.args[0]

    session = Session()
    existing_subscription = (
        session.query(Subscription).filter_by(user_id=user_id, keyword=keyword).first()
    )

    if existing_subscription:
        session.delete(existing_subscription)
        session.commit()
        await update.message.reply_text(
            _('You have unsubscribed from notifications for the keyword "{}".').format(
                keyword
            )
        )
    else:
        await update.message.reply_text(
            _('You are not subscribed to notifications for the keyword "{}".').format(
                keyword
            )
        )

    session.close()


async def list_subscriptions(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_language = user_languages.get(user_id, Language.EN.value[0])
    _ = translations[user_language].gettext

    session = Session()
    subscriptions = session.query(Subscription).filter_by(user_id=user_id).all()
    if subscriptions:
        subscription_list = "\n".join(
            [f"{sub.keyword} ({sub.language})" for sub in subscriptions]
        )
        await update.message.reply_text(
            _("Your subscriptions:\n{}").format(subscription_list)
        )
    else:
        await update.message.reply_text(_("You have no subscriptions."))

    session.close()
