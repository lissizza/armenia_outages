import asyncio
from datetime import datetime
import gettext
import logging
import json
import os
from telegram.error import RetryAfter
from utils import escape_markdown_v2
from models import EventType, Language, ProcessedEvent
from db import Session
from config import CHANNEL_ID_AM, CHANNEL_ID_EN, CHANNEL_ID_RU, REDIS_URL
import redis

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

    return title


def generate_house_numbers_section(house_numbers, _):
    """Helper function to generate the house numbers section."""
    if house_numbers:
        house_numbers = ", ".join(
            [num for num in house_numbers.split(", ") if num.strip()]
        )
        return _("House Numbers: {}\n").format(house_numbers)
    return ""


def generate_message(event):
    """Function to generate a message from a processed event."""
    lang_code = event.language.value[0]
    translation = translations[lang_code]
    translation.install()
    _ = translation.gettext

    title = generate_title(event.event_type, event.planned, event.language)
    title = f"*{escape_markdown_v2(title)}*\n"
    details = ""
    if event.area:
        details += f"*{escape_markdown_v2(event.area)}*\n"
    if event.start_time:
        details += f"*{escape_markdown_v2(event.start_time)}*\n"
    if event.district:
        details += f"{escape_markdown_v2(event.district)}\n"

    details += generate_house_numbers_section(event.house_numbers, _)

    if event.text:
        details += _("Details: {}\n").format(escape_markdown_v2(event.text))

    message_info = {"event_ids": [event.id], "text": f"{title}{details}"}

    return message_info


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
                        chat_id=channel_id, text=text, parse_mode="MarkdownV2"
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
        title = escape_markdown_v2(
            generate_title(
                events[0].event_type, events[0].planned, events[0].language
            ).strip()
        )

        formatted_area = f"*{escape_markdown_v2(area.strip())}*" if area else ""
        formatted_time = (
            f"*{escape_markdown_v2(start_time.strip())}*" if start_time else ""
        )

        current_message = {
            "text": f"*{title}*\n{formatted_area}\n{formatted_time}\n",
            "event_ids": [event.id for event in events],
        }
        sorted_events = sorted(events, key=lambda e: e.district or "")

        for event in sorted_events:
            if event.district:
                formatted_district = escape_markdown_v2(event.district.strip())
                formatted_house_numbers = generate_house_numbers_section(
                    escape_markdown_v2(event.house_numbers), _
                ).strip()
                event_message = f"{formatted_district}\n{formatted_house_numbers}\n\n"
            else:
                formatted_house_numbers = generate_house_numbers_section(
                    escape_markdown_v2(event.house_numbers), _
                ).strip()
                event_message = f"{formatted_house_numbers}\n\n"

            if len(current_message["text"]) + len(event_message) > 4096:
                messages.append(current_message)
                current_message = {
                    "text": f"{title}\n{formatted_area}\n{formatted_time}\n"
                    + event_message,
                    "event_ids": [event.id],
                }
            else:
                current_message["text"] += event_message
                current_message["event_ids"].append(event.id)

        if current_message["text"]:
            messages.append(current_message)

    return messages


async def process_redis_messages(context) -> None:
    """Check and process any pending messages in the Redis queue."""
    logger.info("Checking for pending messages in the Redis queue...")
    while redis_client.llen("event_queue") > 0:
        await send_grouped_messages(context, delay=1)
    logger.info("Finished processing pending messages.")
