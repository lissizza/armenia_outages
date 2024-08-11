import logging
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from datetime import datetime
from models import Event, EventType, Language
from config import WATER_OUTAGE_URL
from db import Session
from utils import compute_hash_by_text
from parsers.webdriver_utils import start_webdriver, restart_webdriver
from urllib3.exceptions import NewConnectionError, MaxRetryError

# Initialize logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

translator_ru = GoogleTranslator(source="auto", target="ru")
translator_en = GoogleTranslator(source="auto", target="en")


def translate_text(text):
    translation_ru = translator_ru.translate(text)
    translation_en = translator_en.translate(text)
    return translation_ru, translation_en


def parse_and_save_water_events():
    driver = start_webdriver()
    if not driver:
        logger.error("Failed to start WebDriver.")
        return

    try:
        driver.get(WATER_OUTAGE_URL)
    except (NewConnectionError, MaxRetryError) as e:
        logger.error(f"Connection error occurred: {e}")
        driver.quit()
        driver = restart_webdriver()
        if not driver:
            logger.error("Failed to restart WebDriver.")
            return
        try:
            driver.get(WATER_OUTAGE_URL)
        except (NewConnectionError, MaxRetryError) as e:
            logger.error(f"Failed after restarting WebDriver: {e}")
            driver.quit()
            return

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    session = Session()
    new_records_count = 0
    events = []

    for panel in soup.find_all("div", class_="panel"):
        heading = panel.find("div", class_="panel-heading").get_text(strip=True)
        body = panel.find("div", class_="panel-body").get_text(strip=True)
        text = heading + " " + body

        event_hash = compute_hash_by_text(text)

        # Check if the hash already exists in the Event table
        existing_event = session.query(Event).filter_by(hash=event_hash).first()
        if existing_event:
            logger.info(
                f"Hash {event_hash} already exists in the database. Skipping event."
            )
            continue

        translation_ru, translation_en = translate_text(text)

        timestamp = datetime.now().isoformat()

        event_type = EventType.WATER
        planned = "Պլանային" in heading

        event_am = Event(
            event_type=event_type,
            area=None,
            district=None,
            house_number=None,
            start_time=None,
            end_time=None,
            language=Language.AM,
            planned=planned,
            hash=event_hash,
            text=text,
            timestamp=timestamp,
            processed=False,
        )
        event_ru = Event(
            event_type=event_type,
            area=None,
            district=None,
            house_number=None,
            start_time=None,
            end_time=None,
            language=Language.RU,
            planned=planned,
            hash=compute_hash_by_text(translation_ru),
            text=translation_ru,
            timestamp=timestamp,
            processed=False,
        )
        event_en = Event(
            event_type=event_type,
            area=None,
            district=None,
            house_number=None,
            start_time=None,
            end_time=None,
            language=Language.EN,
            planned=planned,
            hash=compute_hash_by_text(translation_en),
            text=translation_en,
            timestamp=timestamp,
            processed=False,
        )

        events.extend([event_am, event_ru, event_en])
        new_records_count += 3

    # Reverse the events list before saving to the database
    events.reverse()
    session.add_all(events)
    session.commit()
    session.close()
    logger.info(f"Added {new_records_count} new water events to the database.")
    driver.quit()


if __name__ == "__main__":
    parse_and_save_water_events()
