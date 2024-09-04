import asyncio
from datetime import datetime
import logging
from telegram.error import RetryAfter, TimedOut, NetworkError
from telegram.ext import CallbackContext
from post_handlers.emergency_power import generate_emergency_power_posts
from post_handlers.water import generate_water_posts
from db import Session
from models import Post, PostType
from parsers.power_parser import parse_emergency_power_events
from parsers.water_parser import parse_water_events
from utils import get_channel_id

logger = logging.getLogger(__name__)

MESSAGE_DELAY = 2  # seconds


async def send_emergency_power_posts(context: CallbackContext) -> None:
    logger.info("Sending unsent power posts...")
    session = Session()

    unsent_emergency_power_posts = (
        session.query(Post)
        .filter(Post.posted_time.is_(None), Post.post_type == PostType.EMERGENCY_POWER)
        .order_by(Post.creation_time)
        .all()
    )

    for post in unsent_emergency_power_posts:
        result = await send_post_to_channel(context, post, session)
        if not result:
            break

    session.close()
    logger.info("Finished sending all unsent power posts.")


async def send_water_posts(context: CallbackContext) -> None:
    logger.info("Sending unsent water posts...")
    session = Session()

    unsent_posts = (
        session.query(Post)
        .filter(
            Post.posted_time.is_(None),
            Post.post_type.in_([PostType.EMERGENCY_WATER, PostType.SCHEDULED_WATER]),
        )
        .order_by(Post.creation_time)
        .all()
    )

    for post in unsent_posts:
        result = await send_post_to_channel(context, post, session)
        if not result:
            break

    session.close()
    logger.info("Finished sending all unsent power posts.")


async def send_post_to_channel(
    context: CallbackContext, post: Post, session: Session
) -> bool:
    try:
        channel_id = get_channel_id(post.language)

        if channel_id:
            await context.bot.send_message(
                chat_id=channel_id, text=post.text, parse_mode="MarkdownV2"
            )
            post.posted_time = datetime.now()
            await asyncio.get_event_loop().run_in_executor(None, session.commit)
            logger.info(f"Sent post ID {post.id} to channel {channel_id}.")
        else:
            logger.error(f"Invalid channel ID for language {post.language}.")
            return False

        await asyncio.sleep(MESSAGE_DELAY)
        return True

    except RetryAfter as e:
        retry_after = e.retry_after
        logger.error(
            f"Flood control exceeded. Retry in {retry_after} seconds for post ID {post.id}."
        )
        await asyncio.sleep(retry_after + MESSAGE_DELAY)
        return await send_post_to_channel(context, post, session)

    except (TimedOut, NetworkError) as e:
        logger.error(
            f"Temporary network error for post ID {post.id}: {e}. Will retry later."
        )
        return False

    except Exception as e:
        logger.error(f"Failed to send post ID {post.id} due to unexpected error: {e}")
        session.rollback()
        return False


async def update_and_create_power_posts(context: CallbackContext) -> None:
    session = Session()

    try:
        logger.info("Checking for updates...")
        await parse_emergency_power_events(session)

        logger.info("Creating emergency power posts...")
        await generate_emergency_power_posts(session)
    finally:
        session.close()


async def update_and_create_water_posts(context: CallbackContext) -> None:
    session = Session()
    try:
        logger.info("Parsing water updates")
        await parse_water_events(session)

        logger.info("Creating water posts...")
        await generate_water_posts(session)
    finally:
        session.close()
