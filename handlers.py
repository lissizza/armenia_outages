import gettext
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from db import Session
from models import Event, Subscription, Language
from parser import fetch_electricity_outages, fetch_water_outages, translate_event


languages = [lang.value for lang in Language]
translations = {}
for lang in languages:
    try:
        translations[lang] = gettext.translation(
            "messages", localedir="locales", languages=[lang], fallback=True
        )
    except Exception as e:
        print(f"Error loading translation for {lang}: {e}")

user_languages = {}


async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_languages[user_id] = Language.EN.value
    _ = translations[Language.EN.value].gettext

    keyboard = [
        [
            InlineKeyboardButton("English", callback_data="set_language en"),
            InlineKeyboardButton("Русский", callback_data="set_language ru"),
            InlineKeyboardButton("Հայերեն", callback_data="set_language am"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        _(
            "Hello! I am a bot that tracks water and electricity outages. Please choose your language."
        ),
        reply_markup=reply_markup,
    )


async def set_language(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    lang_code = query.data.split()[1]
    if lang_code not in translations:
        _ = translations[user_languages.get(user_id, Language.EN.value)].gettext
        await query.edit_message_text(_("Invalid language choice."))
        return

    user_languages[user_id] = lang_code
    _ = translations[user_languages[user_id]].gettext
    await query.edit_message_text(_("Language has been set to {}").format(lang_code))


async def subscribe(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_language = user_languages.get(user_id, Language.EN.value)
    _ = translations[user_language].gettext

    if len(context.args) < 1:
        await update.message.reply_text(_("Usage: /subscribe <keyword>"))
        return

    keyword = context.args[0]

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
    user_language = user_languages.get(user_id, Language.EN.value)
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
    user_language = user_languages.get(user_id, Language.EN.value)
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


async def check_for_updates(context: CallbackContext):
    bot = context.bot
    session = Session()
    new_events = fetch_electricity_outages(Language.RU.value) + fetch_water_outages()

    for event in new_events:
        if event["language"] != Language.AM.value:
            translated_event = translate_event(event, Language.AM.value)
            session.add(Event(**translated_event))
    session.commit()

    subscriptions = session.query(Subscription).all()
    for subscription in subscriptions:
        for event in new_events:
            if subscription.keyword.lower() in event["description"].lower():
                translated_event = translate_event(event, subscription.language)
                await bot.send_message(
                    subscription.user_id,
                    text=f"Subscription: {subscription.keyword}\n{translated_event}",
                )

    session.close()
