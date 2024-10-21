import asyncio
from datetime import datetime, timedelta
import logging
from telegram.error import RetryAfter, TimedOut, NetworkError
from telegram.ext import CallbackContext
from post_handlers.emergency_power import generate_emergency_power_posts
from post_handlers.water import generate_water_posts
from db import session_scope
from models import Event, Post, PostType
from parsers.power_parser import parse_emergency_power_events
from parsers.water_parser import parse_water_events
from utils import get_channel_id

logger = logging.getLogger(__name__)

MESSAGE_DELAY = 2  # seconds


async def send_emergency_power_posts(context: CallbackContext) -> None:
    logger.info("Sending unsent power posts...")
    async with session_scope() as session:
        unsent_emergency_power_posts = await session.execute(
            session.query(Post)
            .filter(
                Post.posted_time.is_(None), Post.post_type == PostType.EMERGENCY_POWER
            )
            .order_by(Post.creation_time)
        )
        unsent_emergency_power_posts = unsent_emergency_power_posts.scalars().all()

        for post in unsent_emergency_power_posts:
            result = await send_post_to_channel(context, post, session)
            if not result:
                break

        logger.info("Finished sending all unsent power posts.")


async def send_water_posts(context: CallbackContext) -> None:
    logger.info("Sending unsent water posts...")
    async with session_scope() as session:
        unsent_posts = await session.execute(
            session.query(Post)
            .filter(
                Post.posted_time.is_(None),
                Post.post_type.in_(
                    [PostType.EMERGENCY_WATER, PostType.SCHEDULED_WATER]
                ),
            )
            .order_by(Post.creation_time)
        )
        unsent_posts = unsent_posts.scalars().all()

        for post in unsent_posts:
            result = await send_post_to_channel(context, post, session)
            if not result:
                break

        logger.info("Finished sending all unsent water posts.")


async def send_post_to_channel(context: CallbackContext, post: Post, session) -> bool:
    try:
        channel_id = get_channel_id(post.language)

        if channel_id:
            await context.bot.send_message(
                chat_id=channel_id, text=post.text, parse_mode="MarkdownV2"
            )
            post.posted_time = datetime.now()
            await session.commit()
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
        await session.rollback()
        return False


async def update_and_create_power_posts(context: CallbackContext) -> None:
    async with session_scope() as session:
        logger.info("Checking for updates...")
        await parse_emergency_power_events(session)

        logger.info("Creating emergency power posts...")
        await generate_emergency_power_posts(session)


async def update_and_create_water_posts(context: CallbackContext) -> None:
    async with session_scope() as session:
        logger.info("Parsing water updates")
        await parse_water_events(session)

        logger.info("Creating water posts...")
        await generate_water_posts(session)


async def cleanup_outdated_events(context: CallbackContext) -> None:
    logger.info("Starting cleanup of outdated events from the database.")
    async with session_scope() as session:
        try:
            threshold_time = datetime.now() - timedelta(days=3)

            while True:
                outdated_events = await session.execute(
                    session.query(Event)
                    .filter(Event.timestamp < threshold_time)
                    .limit(1000)
                )
                outdated_events = outdated_events.scalars().all()

                if not outdated_events:
                    break

                event_ids = [event.id for event in outdated_events]
                await session.execute(
                    session.query(Event)
                    .filter(Event.id.in_(event_ids))
                    .delete(synchronize_session=False)
                )
                await session.commit()

                logger.info(f"Deleted {len(outdated_events)} outdated events.")

            logger.info("Cleanup of outdated events completed successfully.")
        except Exception as e:
            await session.rollback()
            logger.error(f"Error during cleanup of outdated events: {e}")
