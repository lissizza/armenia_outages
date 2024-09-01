import signal
import nest_asyncio
import logging
import asyncio
import httpx
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    InlineQueryHandler,
)
from telegram.error import Forbidden, NetworkError
from config import (
    CHECK_FOR_POWER_UPDATES_INTERVAL,
    CHECK_FOR_WATER_UPDATES_INTERVAL,
    POST_UPDATES_INTERVAL,
    TOKEN,
)
from db import init_db
from action_handlers.handlers import (
    start,
    set_language,
)
from action_handlers.subscribe_handlers import (
    inline_query,
    subscribe_handler,
    subscription_list,
    unsubscribe_callback,
)
from tasks import (
    post_updates,
    update_and_create_power_posts,
    update_and_create_water_posts,
)

nest_asyncio.apply()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.DEBUG
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: CallbackContext) -> None:
    try:
        raise context.error
    except Forbidden:
        logger.warning(f"Bot was blocked by user {update.effective_user.id}")
    except NetworkError as e:
        logger.error(f"Network error occurred: {e}. Retrying...")
        await asyncio.sleep(5)
    except Exception as e:
        logger.error(
            msg=f"An error occurred while handling an update: {e}",
            exc_info=context.error,
        )


async def set_commands(application):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("subscribe", "Subscribe to notifications"),
        BotCommand("subscription_list", "List your current subscriptions"),
    ]
    await application.bot.set_my_commands(commands)


async def periodic_task(interval, task_func, context: CallbackContext):
    while True:
        try:
            await task_func(context)
        except Exception as e:
            logger.error(f"Error in {task_func.__name__}: {e}")
        await asyncio.sleep(interval)


async def main() -> None:
    init_db()
    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    timeout = httpx.Timeout(20.0)

    httpx_client = httpx.AsyncClient(limits=limits, timeout=timeout)

    application = Application.builder().token(TOKEN).build()
    application.bot._httpx_client = httpx_client

    await set_commands(application)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CallbackQueryHandler(set_language, pattern="^set_language ")
    )
    application.add_handler(subscribe_handler)
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CommandHandler("subscription_list", subscription_list))
    application.add_handler(
        CallbackQueryHandler(unsubscribe_callback, pattern=r"^unsubscribe_\d+$")
    )

    application.add_error_handler(error_handler)

    logger.info("Bot started and ready to receive commands")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    context = CallbackContext(application)
    asyncio.create_task(
        periodic_task(
            CHECK_FOR_POWER_UPDATES_INTERVAL, update_and_create_power_posts, context
        )
    )
    asyncio.create_task(
        periodic_task(
            CHECK_FOR_WATER_UPDATES_INTERVAL, update_and_create_water_posts, context
        )
    )
    asyncio.create_task(periodic_task(POST_UPDATES_INTERVAL, post_updates, context))

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler(sig):
        logger.info(f"Received exit signal {sig.name}...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler, sig)

    await stop_event.wait()

    logger.info("Stopping application...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    await httpx_client.aclose()
    logger.info("Application stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())
