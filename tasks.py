from datetime import datetime
import logging
import asyncio
import gettext
import os
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from telegram.ext import CallbackContext
from telegram.error import RetryAfter
from parsers.power_parser import parse_emergency_power_events
from parsers.water_parser import parse_and_save_water_events
from models import EventType, Language, Event, ProcessedEvent
from db import Session
from config import CHANNEL_ID_AM, CHANNEL_ID_RU, CHANNEL_ID_EN, REDIS_URL
import redis

from utils import translate_text

# Configurable delay between messages
MESSAGE_DELAY = 2  # seconds

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

redis_client = redis.StrictRedis.from_url(REDIS_URL)

# Translation files setup
locales_dir = os.path.join(os.path.dirname(__file__), "locales")
translations = {
    "am": gettext.translation("messages", locales_dir, languages=["am"]),
    "ru": gettext.translation("messages", locales_dir, languages=["ru"]),
    "en": gettext.translation("messages", locales_dir, languages=["en"]),
}


def get_channel_id(language):
    if language == Language.AM:
        return CHANNEL_ID_AM
    elif language == Language.RU:
        return CHANNEL_ID_RU
    elif language == Language.EN:
        return CHANNEL_ID_EN
    return None


def generate_message(event):
    """Function to generate a message from a processed event"""
    lang_code = event.language.value[0]
    translation = translations[lang_code]
    translation.install()
    _ = translation.gettext

    if event.event_type == EventType.WATER:
        if event.planned:
            title = _("Scheduled water outage")
        else:
            title = _("Emergency water outage")
    elif event.event_type == EventType.POWER:
        if event.planned:
            title = _("Scheduled power outage")
        else:
            title = _("Emergency power outage")
    elif event.event_type == EventType.GAS:
        if event.planned:
            title = _("Scheduled gas outage")
        else:
            title = _("Emergency gas outage")

    title = f"**{title}**\n"

    details = ""
    if event.area:
        details += _("Area: {}\n").format(event.area)
    if event.district:
        details += _("District: {}\n").format(event.district)
    if event.house_numbers:
        details += _("House Numbers: {}\n").format(event.house_numbers)
    if event.start_time:
        details += _("Start Time: {}\n").format(event.start_time)
    if event.end_time:
        details += _("End Time: {}\n").format(event.end_time)
    if event.text:
        details += _("Details: {}\n").format(event.text)

    return f"{title}{details}"


async def send_message(context, delay):
    """Function to send messages from the Redis queue"""
    while True:
        event_id = redis_client.lpop("event_queue")
        if event_id is None:
            await asyncio.sleep(delay)
            continue

        event_id = int(event_id.decode("utf-8"))

        session = Session()
        try:
            event = session.query(ProcessedEvent).get(event_id)
            if not event:
                logger.error(f"Processed event with ID {event_id} not found.")
                continue

            if event.sent:
                logger.info(f"Event {event_id} has already been sent. Skipping.")
                continue

            message = generate_message(event)
            channel_id = get_channel_id(event.language)

            if channel_id:
                try:
                    await context.bot.send_message(
                        chat_id=channel_id, text=message, parse_mode="Markdown"
                    )
                    event.sent = True
                    event.sent_time = datetime.now().isoformat()
                    session.commit()
                    logger.info(
                        f"Sent processed event {event.id} to channel {channel_id}: {message}"
                    )
                except RetryAfter as e:
                    retry_after = e.retry_after
                    logger.error(
                        f"Flood control exceeded. Retry in {retry_after} seconds."
                    )
                    await asyncio.sleep(retry_after)
                    if not event.sent:
                        redis_client.lpush("event_queue", event_id)
                except Exception as e:
                    logger.error(
                        f"Failed to send message for processed event {event.id}: {e}"
                    )
                    redis_client.lpush("event_queue", event_id)
            else:
                logger.error(f"Invalid language for processed event {event.id}")
        except Exception as e:
            logger.error(f"Failed to send message for processed event {event_id}: {e}")
        finally:
            session.close()
            await asyncio.sleep(delay)


async def post_updates(context: CallbackContext) -> None:
    """Function to queue unsent processed events and start the message sending process"""
    logger.info("Posting updates to the channel...")
    session = Session()
    unsent_events = (
        session.query(ProcessedEvent)
        .filter_by(sent=False)
        .order_by(ProcessedEvent.start_time)
        .all()
    )

    for event in unsent_events:
        redis_client.rpush("event_queue", event.id)

    session.commit()
    session.close()
    logger.info("Finished posting updates")

    asyncio.create_task(send_message(context, MESSAGE_DELAY))


async def check_for_updates(context: CallbackContext) -> None:
    """Function to check for updates and process new events"""
    logger.info("Checking for updates...")
    try:
        for language in Language:
            logger.info(f"Parsing power updates for language: {language.name}")
            parse_emergency_power_events(
                EventType.POWER, planned=False, language=language
            )

        logger.info("Parsing water updates")
        parse_and_save_water_events()

        update_processed_events()

    except Exception as e:
        logger.error(f"Error while checking for updates: {e}")


def process_emergency_power_events(session):
    """
    Aggregate emergency power events by combining house numbers for events with the same
    start time, area, district, language, and event type. Marks the original events as processed.
    """
    unprocessed_emergency_power_events = (
        session.query(
            Event.start_time,
            Event.area,
            Event.district,
            Event.language,
            Event.event_type,
            func.group_concat(Event.house_number, ", ").label("house_numbers"),
        )
        .filter(
            Event.processed == 0,
            Event.event_type == EventType.POWER,
            Event.planned == 0,
            (Event.area.isnot(None))
            | (Event.district.isnot(None))
            | (Event.house_number.isnot(None)),
        )
        .group_by(
            Event.start_time,
            Event.area,
            Event.district,
            Event.language,
            Event.event_type,
        )
        .all()
    )

    for event in unprocessed_emergency_power_events:
        processed_event = ProcessedEvent(
            start_time=event.start_time,
            area=event.area,
            district=event.district,
            house_numbers=event.house_numbers,
            language=event.language,
            event_type=event.event_type,
            planned=False,
            sent=False,
            timestamp=datetime.now().isoformat(),
        )

        try:
            session.add(processed_event)
            event.processed = True
            session.commit()

        except IntegrityError:
            session.rollback()
            existing_event = (
                session.query(ProcessedEvent)
                .filter_by(
                    start_time=event.start_time,
                    area=event.area,
                    district=event.district,
                    language=event.language,
                    event_type=event.event_type,
                    planned=False,
                )
                .first()
            )

            if existing_event:
                existing_event.house_numbers = ", ".join(
                    sorted(
                        set(
                            filter(None, existing_event.house_numbers.split(", "))
                            + filter(None, event.house_numbers.split(", "))
                        )
                    )
                )
                existing_event.sent = False
                existing_event.timestamp = datetime.now().isoformat()
                session.commit()

                event.processed = True
                session.commit()
        else:
            logger.error(
                f"Expected existing event not found after IntegrityError for "
                f"{event.start_time}, {event.area}, {event.district}, {event.language}, {event.event_type}"
            )


def process_water_events(session):
    """
    Process water events by directly transferring them from the events table
    to the processed_events table, including translation for RU and EN.
    Marks the original events as processed.
    """
    unprocessed_water_events = (
        session.query(Event)
        .filter(
            Event.processed == 0,
            Event.event_type == EventType.WATER,
            Event.language == Language.AM,
        )
        .all()
    )

    for event in unprocessed_water_events:
        # Translate the text
        translation_ru, translation_en = translate_text(event.text)

        # Create processed events for all three languages
        processed_event_am = ProcessedEvent(
            start_time=event.start_time,
            area=event.area,
            district=event.district,
            house_numbers=event.house_number,
            language=Language.AM,
            event_type=event.event_type,
            planned=event.planned,
            sent=False,
            timestamp=datetime.now().isoformat(),
            text=event.text,
        )

        processed_event_ru = ProcessedEvent(
            start_time=event.start_time,
            area=event.area,
            district=event.district,
            house_numbers=event.house_number,
            language=Language.RU,
            event_type=event.event_type,
            planned=event.planned,
            sent=False,
            timestamp=datetime.now().isoformat(),
            text=translation_ru,
        )

        processed_event_en = ProcessedEvent(
            start_time=event.start_time,
            area=event.area,
            district=event.district,
            house_numbers=event.house_number,
            language=Language.EN,
            event_type=event.event_type,
            planned=event.planned,
            sent=False,
            timestamp=datetime.now().isoformat(),
            text=translation_en,
        )

        try:
            session.add_all(
                [processed_event_am, processed_event_ru, processed_event_en]
            )
            session.commit()

            event.processed = True
            session.commit()

        except IntegrityError:
            session.rollback()
            logger.error(
                f"Failed to insert water event {event.id} due to IntegrityError"
            )


def update_processed_events():
    """
    Update the processed events by aggregating emergency power events
    and directly processing water events.
    """
    session = Session()
    try:
        logger.info("Updating processed events...")

        process_emergency_power_events(session)
        process_water_events(session)

        logger.info("Processed events updated successfully.")

    except Exception as e:
        logger.error(f"Failed to update processed events: {e}")
        session.rollback()
    finally:
        session.close()
