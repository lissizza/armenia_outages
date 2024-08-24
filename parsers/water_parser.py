import asyncio
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException
from config import WATER_OUTAGE_URL
from parsers.webdriver_utils import start_webdriver_async
from utils import compute_hash_by_text
from db import Session
from models import Event, EventType, Language

logger = logging.getLogger(__name__)


async def parse_water_events():
    driver = await start_webdriver_async()
    if not driver:
        logger.error("Failed to start WebDriver.")
        return

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, driver.get, WATER_OUTAGE_URL
        )
    except WebDriverException as e:
        logger.error(f"WebDriver error occurred: {e}")
        await asyncio.get_event_loop().run_in_executor(None, driver.quit)
        return

    html = await asyncio.get_event_loop().run_in_executor(
        None, lambda: driver.page_source
    )
    soup = BeautifulSoup(html, "html.parser")

    session = Session()
    new_records_count = 0
    events = []

    for panel in soup.find_all("div", class_="panel"):
        heading = panel.find("div", class_="panel-heading").get_text(strip=True)
        body = panel.find("div", class_="panel-body").get_text(strip=True)
        text = heading + " " + body

        event_hash = compute_hash_by_text(text)

        existing_event = session.query(Event).filter_by(hash=event_hash).first()
        if existing_event:
            logger.info(
                f"Hash {event_hash} already exists in the database. Skipping event and stop parsing."
            )
            break

        timestamp = datetime.now()
        planned = "Պլանային" in heading

        event_am = Event(
            event_type=EventType.WATER,
            area=None,
            district=None,
            house_number=None,
            start_time=None,
            end_time=None,
            language=Language.HY,
            planned=planned,
            hash=event_hash,
            text=text,
            timestamp=timestamp,
            processed=False,
        )

        events.append(event_am)
        new_records_count += 1

    # Reverse the events list before saving to the database
    events.reverse()
    session.add_all(events)
    session.commit()
    session.close()
    logger.info(f"Added {new_records_count} new water events to the database.")

    await asyncio.get_event_loop().run_in_executor(None, driver.quit)


if __name__ == "__main__":
    asyncio.run(parse_water_events())
