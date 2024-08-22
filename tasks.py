import asyncio
import json
import logging
from telegram.ext import CallbackContext
from handle_events import process_emergency_power_events, process_water_events
from handle_posts import (
    generate_message,
    generate_emergency_power_messages,
)
from db import Session
from models import EventType, Language, ProcessedEvent
from config import REDIS_URL
import redis

from parsers.power_parser import (
    parse_emergency_power_events,
    parse_planned_power_events,
)
from parsers.water_parser import parse_water_events
from send_posts import send_grouped_messages

logger = logging.getLogger(__name__)
redis_client = redis.StrictRedis.from_url(REDIS_URL)

MESSAGE_DELAY = 2  # seconds


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
            grouped_messages = generate_emergency_power_messages(emergency_events)
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

    logger.info("Parsing planned power updates")
    parse_planned_power_events()
