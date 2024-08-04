import signal
import nest_asyncio
import logging
import asyncio
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
from tasks import check_for_updates

nest_asyncio.apply()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


async def main() -> None:
    init_db()
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CallbackQueryHandler(set_language, pattern="^set_language ")
    )
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("list_subscriptions", list_subscriptions))

    job_queue = application.job_queue
    job_queue.run_repeating(check_for_updates, interval=3600, first=3600)

    application.add_error_handler(error_handler)

    logger.info("Bot started and ready to receive commands")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    context = CallbackContext(application)
    asyncio.create_task(check_for_updates(context))

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
    logger.info("Application stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())
