from datetime import datetime
import json
import logging
import asyncio
import gettext
import os
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from telegram.ext import CallbackContext
from telegram.error import RetryAfter
from parsers.power_parser import parse_emergency_power_events
from parsers.water_parser import parse_water_events
from models import EventType, Language, Event, ProcessedEvent
from db import Session
from config import CHANNEL_ID_AM, CHANNEL_ID_RU, CHANNEL_ID_EN, REDIS_URL
import redis

from utils import translate_text

# Configurable delay between messages
MESSAGE_DELAY = 2  # seconds

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


def generate_title(event_type, planned, language):
    """Generate the title for a message based on the event type and language."""
    translation = translations[language.value[0]]
    translation.install()
    _ = translation.gettext

    if event_type == EventType.WATER:
        title = _("Scheduled water outage") if planned else _("Emergency water outage")
    elif event_type == EventType.POWER:
        title = _("Scheduled power outage") if planned else _("Emergency power outage")
    elif event_type == EventType.GAS:
        title = _("Scheduled gas outage") if planned else _("Emergency gas outage")

    return f"**{title}**\n"


def generate_house_numbers_section(house_numbers, _):
    """Helper function to generate the house numbers section."""
    if house_numbers:
        return _("House Numbers: {}\n").format(house_numbers)
    return ""


def generate_message(event):
    """Функция для генерации сообщения из обработанного события"""
    lang_code = event.language.value[0]
    translation = translations[lang_code]
    translation.install()
    _ = translation.gettext

    title = generate_title(event.event_type, event.planned, event.language)

    details = ""
    if event.area:
        details += _("Area: {}\n").format(event.area)
    if event.district:
        details += _("District: {}\n").format(event.district)
    details += generate_house_numbers_section(event.house_numbers, _)

    if event.start_time:
        details += _("Start Time: {}\n").format(event.start_time)
    if event.end_time:
        details += _("End Time: {}\n").format(event.end_time)
    if event.text:
        details += _("Details: {}\n").format(event.text)

    # Создаем словарь с правильными ключами
    message_info = {"event_ids": [event.id], "text": f"{title}{details}"}

    return message_info


async def send_message(context, delay):
    """Function to send messages from the Redis queue"""
    while True:
        event_data = redis_client.lpop("event_queue")
        if event_data is None:
            await asyncio.sleep(delay)
            continue

        try:
            message_info = json.loads(event_data.decode("utf-8"))
            event_id = message_info.get("event_id")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode event data: {e}")
            continue

        session = Session()
        try:
            event = session.query(ProcessedEvent).get(event_id)
            if not event:
                logger.error(f"Processed event with ID {event_id} not found.")
                continue

            if event.sent:
                logger.info(f"Event {event_id} has already been sent. Skipping.")
                continue

            message = message_info.get("message")
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
                        redis_client.rpush("event_queue", json.dumps(message_info))
                except Exception as e:
                    logger.error(
                        f"Failed to send message for processed event {event.id}: {e}"
                    )
                    redis_client.rpush("event_queue", json.dumps(message_info))
            else:
                logger.error(f"Invalid language for processed event {event.id}")
        except Exception as e:
            logger.error(f"Failed to send message for processed event {event_id}: {e}")
        finally:
            session.close()
            await asyncio.sleep(delay)


def generate_grouped_messages(events):
    """Generate grouped messages by area and start_time from a list of processed events"""
    if not events:
        return []

    first_event = events[0]
    lang_code = first_event.language.value[0]
    translation = translations[lang_code]
    translation.install()
    _ = translation.gettext

    grouped_events = {}
    for event in events:
        group_key = (event.area, event.start_time)
        if group_key not in grouped_events:
            grouped_events[group_key] = []
        grouped_events[group_key].append(event)

    messages = []
    for (area, start_time), events in grouped_events.items():
        title = generate_title(
            events[0].event_type, events[0].planned, events[0].language
        )
        current_message = {
            "text": f"**{title}**\n**{area}**\n**{start_time}**\n\n",
            "event_ids": [event.id for event in events],
        }
        sorted_events = sorted(events, key=lambda e: e.district or "")

        for event in sorted_events:
            if event.district:
                event_message = f"{event.district}\n{generate_house_numbers_section(event.house_numbers, _)}\n\n"
            else:
                event_message = (
                    f"{generate_house_numbers_section(event.house_numbers, _)}\n\n"
                )

            if len(current_message["text"]) + len(event_message) > 4096:
                messages.append(current_message)
                current_message = {
                    "text": f"**{title}**\n**{area}**\n**{start_time}**\n\n"
                    + event_message,
                    "event_ids": [event.id],
                }
            else:
                current_message["text"] += event_message
                current_message["event_ids"].append(event.id)

        if current_message["text"]:
            messages.append(current_message)

    return messages


async def send_grouped_messages(context, delay):
    """Function to send grouped messages by area from the Redis queue"""
    while True:
        message_info = redis_client.lpop("event_queue")
        if not message_info:
            await asyncio.sleep(delay)
            continue

        try:
            message_info = json.loads(message_info.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from message_info: {e}")
            continue

        if not isinstance(message_info, dict):
            logger.error(
                f"Invalid format for message_info, expected a dictionary: {message_info}"
            )
            continue

        # Используем правильные ключи
        event_ids = message_info.get("event_ids")
        text = message_info.get("text")

        if not event_ids or not text:
            logger.error(
                f"Invalid message_info received: event_ids={event_ids}, text={text}. Full message_info: {message_info}"
            )
            continue

        session = Session()
        try:
            events = (
                session.query(ProcessedEvent)
                .filter(ProcessedEvent.id.in_(event_ids))
                .all()
            )
            if not events:
                logger.error("No processed events found for provided IDs.")
                continue

            channel_id = get_channel_id(events[0].language)

            if channel_id:
                try:
                    await context.bot.send_message(
                        chat_id=channel_id, text=text, parse_mode="Markdown"
                    )
                    for event in events:
                        event.sent = True
                        event.sent_time = datetime.now().isoformat()
                    session.commit()
                    logger.info(f"Sent grouped message to channel {channel_id}")
                except RetryAfter as e:
                    retry_after = e.retry_after
                    logger.error(
                        f"Flood control exceeded. Retry in {retry_after} seconds."
                    )
                    await asyncio.sleep(retry_after)
                    if not event.sent:
                        redis_client.rpush("event_queue", json.dumps(message_info))
                    session.commit()
                except Exception as e:
                    logger.error(f"Failed to send grouped message: {e}")
                    redis_client.rpush("event_queue", json.dumps(message_info))
                    session.commit()
            else:
                logger.error("Invalid language for processed events")

        except Exception as e:
            logger.error(f"Failed to send grouped messages: {e}")
        finally:
            session.close()
            await asyncio.sleep(delay)


async def post_updates(context: CallbackContext) -> None:
    logger.info("Posting updates to the channel...")
    session = Session()

    for language in Language:
        emergency_events = (
            session.query(ProcessedEvent)
            .filter_by(
                sent=False, language=language, event_type=EventType.POWER, planned=False
            )
            .order_by(ProcessedEvent.start_time)
            .all()
        )

        if emergency_events:
            grouped_messages = generate_grouped_messages(emergency_events)
            for message_info in grouped_messages:
                redis_client.rpush("event_queue", json.dumps(message_info))

        other_events = (
            session.query(ProcessedEvent)
            .filter_by(sent=False, language=language)
            .filter(ProcessedEvent.event_type != EventType.POWER)
            .order_by(ProcessedEvent.start_time)
            .all()
        )

        for event in other_events:
            message_info = generate_message(event)
            if isinstance(message_info, dict):
                redis_client.rpush("event_queue", json.dumps(message_info))
            else:
                logger.error(
                    f"Invalid format for message_info, expected a dictionary: {message_info}"
                )

    session.commit()
    session.close()
    logger.info("Finished posting updates")

    asyncio.create_task(send_grouped_messages(context, MESSAGE_DELAY))


async def check_for_updates(context: CallbackContext) -> None:
    """Function to check for updates and process new events"""
    logger.info("Checking for updates...")
    for language in Language:
        logger.info(f"Parsing emergency power updates for language: {language.name}")
        parse_emergency_power_events(EventType.POWER, planned=False, language=language)

    logger.info("Processing emergency power events...")
    process_emergency_power_events()

    logger.info("Parsing water updates")
    parse_water_events()

    logger.info("Processing water events...")
    process_water_events()


def process_emergency_power_events():
    session = Session()
    try:
        unprocessed_emergency_power_events = (
            session.query(
                Event.id,
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
            logger.info(
                f"Searching for existing event with start_time={event.start_time}, "
                f"area={event.area}, district={event.district}, language={event.language}"
            )

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
                logger.info(f"Found existing event: {existing_event}")
                # Добавьте логирование здесь
                logger.info(f"Trying to mark event with ID {event.id} as processed.")
                existing_house_numbers = list(
                    filter(None, existing_event.house_numbers.split(", "))
                )
                new_house_numbers = list(filter(None, event.house_numbers.split(", ")))

                existing_event.house_numbers = ", ".join(
                    sorted(set(existing_house_numbers + new_house_numbers))
                )
                existing_event.sent = False
                existing_event.timestamp = datetime.now().isoformat()

                session.commit()
            else:
                logger.info(
                    f"Inserting new processed event with start_time={event.start_time}, "
                    f"area={event.area}, district={event.district}, language={event.language}"
                )
                # Добавьте логирование здесь
                logger.info(f"Event data: {event}")

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
                session.add(processed_event)
                session.commit()
                logger.info(
                    f"Inserted new processed event with ID {processed_event.id}"
                )

            try:
                session.query(Event).filter(Event.id == event.id).update(
                    {"processed": True}
                )
                session.commit()
                logger.info(
                    f"Marked event with ID {event.id} as processed and committed."
                )
            except Exception as e:
                logger.error(
                    f"Failed to mark event with ID {event.id} as processed: {e}"
                )
                session.rollback()

    except IntegrityError as e:
        session.rollback()
        logger.error(f"IntegrityError: {e}")
    finally:
        session.close()


def process_water_events():
    """
    Process water events by directly transferring them from the events table
    to the processed_events table, including translation for RU and EN.
    Marks the original events as processed.
    """
    session = Session()
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
    session.close()
