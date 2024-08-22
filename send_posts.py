from db import Session
from handle_posts import get_channel_id, logger, redis_client
from models import ProcessedEvent


from telegram.error import RetryAfter


import asyncio
import json
from datetime import datetime


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


async def process_redis_messages(context) -> None:
    """Check and process any pending messages in the Redis queue."""
    logger.info("Checking for pending messages in the Redis queue...")
    while redis_client.llen("event_queue") > 0:
        await send_grouped_messages(context, delay=1)
    logger.info("Finished processing pending messages.")
