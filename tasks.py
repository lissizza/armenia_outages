import logging
from telegram.ext import CallbackContext
from parser import parse_all_pages
from models import EventType, Language
from db import Session
from models import Event
from config import CHANNEL_ID

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def check_for_updates(context: CallbackContext) -> None:
    logger.info("Checking for updates...")
    try:
        for language in Language:
            logger.info(f"Parsing updates for language: {language.name}")
            parse_all_pages(EventType.ELECTRICITY, planned=False, language=language)
        await post_updates(context)
    except Exception as e:
        logger.error(f"Error while checking for updates: {e}")


async def post_updates(context: CallbackContext) -> None:
    logger.info("Posting updates to the channel...")
    session = Session()
    unsent_events = session.query(Event).filter_by(sent=False).all()

    for event in unsent_events:
        try:
            message = f"""
Type: {event.event_type.value}
Area: {event.area}
District: {event.district}
House Number: {event.house_number}
Start Time: {event.start_time}
End Time: {event.end_time}
"""
            await context.bot.send_message(chat_id=CHANNEL_ID, text=message)
            event.sent = True
            logger.info(f"Sent event {event.id} to channel: {message}")
        except Exception as e:
            logger.error(f"Failed to send message for event {event.id}: {e}")

    session.commit()
    session.close()
    logger.info("Finished posting updates")
