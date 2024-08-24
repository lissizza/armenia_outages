import asyncio
import logging
from datetime import datetime, timedelta
from urllib3.exceptions import NewConnectionError, MaxRetryError
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from models import Event, EventType, Language
from config import POWER_OUTAGE_URL
from db import Session
from utils import compute_hash, normalize_string
from parsers.webdriver_utils import start_webdriver_async, restart_webdriver_async

logger = logging.getLogger(__name__)


def split_address(address):
    parts = address.split(",")
    if len(parts) == 1:
        return parts[0].strip(), None, None
    area = parts[0].strip()
    right_part = parts[1].strip()
    if " " in right_part:
        last_part = right_part.split(" ")[-1]
        if last_part.isdigit():
            district = right_part.rsplit(" ", 1)[0]
            house_number = last_part
            return area, district, house_number
        else:
            return area, right_part, None
    return area, None, right_part if right_part.isdigit() else None


def filter_by_date(event_date_str):
    try:
        event_date = datetime.strptime(event_date_str, "%d.%m.%Y %H:%M")
        current_date = datetime.now()
        return current_date - event_date <= timedelta(days=1)
    except ValueError:
        return False


async def parse_emergency_power_events():
    """
    Asynchronously parse power outages data for all supported languages.
    """
    for language in Language:
        logger.info(f"Parsing emergency power updates for language: {language.name}")
        driver = None
        try:
            driver = await start_webdriver_async()
        except (NewConnectionError, MaxRetryError) as e:
            logger.error(f"Failed to start WebDriver: {e}")
            try:
                driver = await restart_webdriver_async()
            except (NewConnectionError, MaxRetryError) as e:
                logger.error(f"Failed to restart WebDriver: {e}")
                return

        if driver is None:
            logger.error("WebDriver is not initialized.")
            return

        try:
            driver.get(POWER_OUTAGE_URL.format(lang=language.code))
            logger.info(f"URL: {POWER_OUTAGE_URL.format(lang=language.code)}")

            new_records_count = 0

            while True:
                data = await parse_table_async(driver)
                if not data:
                    break

                session = Session()
                for event in data:
                    area, district, house_number = split_address(event[1])
                    start_time = normalize_string(event[0])
                    area = normalize_string(area)
                    district = normalize_string(district)
                    house_number = normalize_string(house_number)

                    if not filter_by_date(start_time):
                        continue

                    event_hash = compute_hash(
                        EventType.POWER,
                        area,
                        district,
                        house_number,
                        start_time,
                        language,
                        False,
                    )

                    existing_event = (
                        session.query(Event).filter_by(hash=event_hash).first()
                    )
                    if existing_event:
                        continue  # Skip this event, it's already in the database

                    new_event = Event(
                        event_type=EventType.POWER,
                        area=area,
                        district=district,
                        house_number=house_number,
                        start_time=start_time,
                        end_time=None,
                        language=language,
                        planned=False,
                        hash=event_hash,
                        timestamp=datetime.now(),
                    )
                    session.add(new_event)
                    new_records_count += 1

                await asyncio.get_event_loop().run_in_executor(None, session.commit)
                session.close()

                try:
                    next_button = driver.find_element(
                        By.CSS_SELECTOR, "a.paginate_button.next"
                    )
                    if "disabled" in next_button.get_attribute("class"):
                        break
                    next_button.click()
                    await asyncio.sleep(0.5)  # Wait for the next page to load
                except Exception as e:
                    logger.error(f"Error navigating to next page: {e}")
                    break

            logger.info(
                f"Added {new_records_count} new records to the database for language {language}."
            )

        except Exception as e:
            logger.error(f"Error during parsing: {e}")
        finally:
            driver.quit()


async def parse_table_async(driver):
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": "ctl00_ContentPlaceHolder1_vtarayin"})
    if table is None:
        logger.error("Could not find the table on the page.")
        return []
    rows = table.find("tbody").find_all("tr")
    data = []
    for row in rows:
        cols = row.find_all("td")
        cols = [ele.text.strip() for ele in cols]
        data.append(cols)
    return data
