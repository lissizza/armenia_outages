import asyncio
from datetime import datetime
import logging
import re
from bs4 import BeautifulSoup
import aiohttp
from db import session_scope
from utils import compute_hash_by_text
from models import Event, EventType, Language
from config import WATER_OUTAGE_URL
from sqlalchemy.future import select


logger = logging.getLogger(__name__)


def filter_by_date(text):
    """
    Extracts the date from the end of the `text` string and compares it with the current date.

    :param text: The text of the event from which the date is extracted.
    :return: True if the event is current, False otherwise.
    """

    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})թ?\.$", text)
    if date_match:
        event_date_str = date_match.group(1)
        try:
            event_date = datetime.strptime(event_date_str, "%d.%m.%Y").date()
            current_date = datetime.now().date()
            if event_date < current_date:
                logger.info(f"Skipped outdated water event with date {event_date_str}")
                return False
            return True
        except ValueError as e:
            logger.error(f"Error parsing date '{event_date_str}': {e}")
            return False
    else:
        logger.warning("Failed to extract date from water event text")
        return False


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

        existing_event = await session.execute(select(Event).filter_by(hash=event_hash))
        if existing_event.scalars().first():
            logger.info(
                f"Hash {event_hash} already exists in the database. Skipping event and stop parsing."
            )
            break

        timestamp = datetime.now()
        planned = "Պլանային" in heading

        if not filter_by_date(text) and not planned:
            logger.info(f"Event in text '{heading}' was skipped due to date filter.")
            continue

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

    if events:
        events.reverse()
        session.add_all(events)
        await session.commit()
        logger.info(f"Added {new_records_count} new water events to the database.")
    else:
        logger.info("No new water events were found.")


async def main():
    async with session_scope() as session:
        await parse_water_events(session)


if __name__ == "__main__":
    asyncio.run(main())
