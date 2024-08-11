import signal
import nest_asyncio
import logging
import asyncio
import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
)
from config import TOKEN
from db import init_db
from handlers import (
    start,
    set_language,
    subscribe,
    list_subscriptions,
    unsubscribe,
)
from tasks import check_for_updates, post_updates
from config import (
    CHECK_FOR_UPDATES_INTERVAL,
    POST_UPDATES_INTERVAL,
    CHECK_FOR_UPDATES_FIRST,
    POST_UPDATES_FIRST,
)

nest_asyncio.apply()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


async def main() -> None:
    init_db()
    # Configure the HTTPX client
    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    timeout = httpx.Timeout(20.0)

    httpx_client = httpx.AsyncClient(limits=limits, timeout=timeout)

    application = Application.builder().token(TOKEN).build()
    application.bot._httpx_client = httpx_client

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CallbackQueryHandler(set_language, pattern="^set_language ")
    )
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("list_subscriptions", list_subscriptions))

    job_queue = application.job_queue

    job_queue.run_repeating(
        check_for_updates,
        interval=CHECK_FOR_UPDATES_INTERVAL,
        first=CHECK_FOR_UPDATES_FIRST,
    )
    job_queue.run_repeating(
        post_updates, interval=POST_UPDATES_INTERVAL, first=POST_UPDATES_FIRST
    )

    application.add_error_handler(error_handler)

    logger.info("Bot started and ready to receive commands")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

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
