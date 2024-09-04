import asyncio
from datetime import datetime
import logging
from bs4 import BeautifulSoup
import aiohttp
from db import Session
from utils import compute_hash_by_text
from models import Event, EventType, Language
from config import WATER_OUTAGE_URL

logger = logging.getLogger(__name__)


async def fetch_html(url):
    """Fetch the HTML content of the given URL asynchronously using aiohttp."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.text()
            else:
                logger.error(
                    f"Failed to fetch URL {url} with status: {response.status}"
                )
                return None


async def parse_water_events(session):
    """Parse water events from the fetched HTML page."""
    html = await fetch_html(WATER_OUTAGE_URL)
    if not html:
        logger.error("Failed to retrieve HTML content.")
        return

    soup = BeautifulSoup(html, "html.parser")
    new_records_count = 0
    events = []

    for panel in soup.find_all("div", class_="panel"):
        heading = panel.find("div", class_="panel-heading").get_text(strip=True)
        body = panel.find("div", class_="panel-body").get_text(strip=True)
        text = f"{heading}\n\n{body}"

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

    events.reverse()
    session.add_all(events)
    session.commit()
    logger.info(f"Added {new_records_count} new water events to the database.")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(parse_water_events(Session()))
