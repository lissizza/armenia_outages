import time
import logging
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from models import Event, LastPage, EventType, Language
from config import POWER_OUTAGE_URL
from db import Session
from utils import compute_hash, normalize_string
from datetime import datetime
from urllib3.exceptions import NewConnectionError, MaxRetryError
from parsers.webdriver_utils import start_webdriver, restart_webdriver
from datetime import timedelta

logging.basicConfig(level=logging.INFO)


def save_last_page(language, planned, page_number):
    session = Session()
    last_page = (
        session.query(LastPage).filter_by(language=language, planned=planned).first()
    )
    if last_page:
        last_page.page_number = page_number
    else:
        last_page = LastPage(
            page_number=page_number, language=language, planned=planned
        )
        session.add(last_page)
    session.commit()
    session.close()


def load_last_page(language, planned):
    session = Session()
    last_page = (
        session.query(LastPage).filter_by(language=language, planned=planned).first()
    )
    session.close()
    if last_page:
        return last_page.page_number
    return 1


def parse_table(driver):
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": "ctl00_ContentPlaceHolder1_vtarayin"})
    if table is None:
        logging.error("Could not find the table on the page.")
        return []
    rows = table.find("tbody").find_all("tr")
    data = []
    for row in rows:
        cols = row.find_all("td")
        cols = [ele.text.strip() for ele in cols]
        data.append(cols)
    return data


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


# Пример функции из парсера


def parse_all_pages(event_type, planned, language):
    driver = None
    try:
        driver = start_webdriver()
    except (NewConnectionError, MaxRetryError) as e:
        logging.error(f"Failed to start WebDriver: {e}")
        try:
            driver = restart_webdriver()
        except (NewConnectionError, MaxRetryError) as e:
            logging.error(f"Failed to restart WebDriver: {e}")
            return  # If both start and restart fail, exit the function

    if driver is None:
        logging.error("WebDriver is not initialized.")
        return

    last_page_number = 1  # Always start from the first page
    logging.info(f"Language: {language}")
    try:
        driver.get(POWER_OUTAGE_URL.format(lang=language.code))
        logging.info(f"URL: {POWER_OUTAGE_URL.format(lang=language.code)}")

        new_records_count = 0

        while True:
            data = parse_table(driver)
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
                    event_type,
                    area,
                    district,
                    house_number,
                    start_time,
                    language,
                    planned,
                )

                existing_event = session.query(Event).filter_by(hash=event_hash).first()
                if existing_event:
                    continue  # Skip this event, it's already in the database

                new_event = Event(
                    event_type=event_type,
                    area=area,
                    district=district,
                    house_number=house_number,
                    start_time=start_time,
                    end_time=None,
                    language=language,
                    planned=planned,
                    hash=event_hash,
                    timestamp=datetime.now().isoformat(),
                )
                session.add(new_event)
                new_records_count += 1

            session.commit()
            session.close()

            try:
                next_button = driver.find_element(
                    By.CSS_SELECTOR, "a.paginate_button.next"
                )
                if "disabled" in next_button.get_attribute("class"):
                    break
                next_button.click()
                time.sleep(0.5)  # Wait for the next page to load
                last_page_number += 1
                save_last_page(language, planned, last_page_number)
            except Exception as e:
                logging.error(f"Error navigating to next page: {e}")
                break

        logging.info(
            f"Added {new_records_count} new records to the database for language {language}."
        )

    except Exception as e:
        logging.error(f"Error during parsing: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    for language in Language:
        parse_all_pages(EventType.POWER, planned=False, language=language)
