import time
import logging
import hashlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from models import Event, LastPage, EventType, Language
from config import CHROMEDRIVER_PATH, ELECTRICITY_OUTAGE_URL
from db import Session

# Initialize WebDriver
options = webdriver.ChromeOptions()
options.add_argument("--headless")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)


# Save the last page number parsed
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


# Load the last page number parsed
def load_last_page(language, planned):
    session = Session()
    last_page = (
        session.query(LastPage).filter_by(language=language, planned=planned).first()
    )
    session.close()
    if last_page:
        return last_page.page_number
    return 1


# Parse the HTML table
def parse_table():
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


# Split the address into area, district, and house number
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


# Compute a hash for the event
def compute_hash(
    event_type, area, district, house_number, start_time, language, planned
):
    hash_input = f"{event_type}{area}{district}{house_number}{start_time}{language}{planned}".encode(
        "utf-8"
    )
    return hashlib.md5(hash_input).hexdigest()


# Parse all pages and save events
def parse_all_pages(event_type, planned, language):
    last_page_number = load_last_page(language, planned)
    logging.info(f"Last page number: {last_page_number}")
    logging.info(f"Language: {language}")
    driver.get(ELECTRICITY_OUTAGE_URL.format(lang=language.code))
    logging.info(f"URL: {ELECTRICITY_OUTAGE_URL.format(lang=language.code)}")

    for _ in range(last_page_number - 1):
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "a.paginate_button.next")
            next_button.click()
            time.sleep(2)
        except Exception as e:
            logging.error(f"Error navigating to the page {last_page_number}: {e}")
            return

    while True:
        data = parse_table()
        if not data:
            break

        session = Session()
        for event in data:
            area, district, house_number = split_address(event[1])
            event_hash = compute_hash(
                event_type, area, district, house_number, event[0], language, planned
            )

            # Check if the event already exists
            existing_event = session.query(Event).filter_by(hash=event_hash).first()
            if existing_event:
                continue  # Skip this event, it's already in the database

            new_event = Event(
                event_type=event_type,
                area=area,
                district=district,
                house_number=house_number,
                start_time=event[0],
                end_time=None,
                language=language,
                planned=planned,
                hash=event_hash,
            )
            session.add(new_event)
        session.commit()

        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "a.paginate_button.next")
            if "disabled" in next_button.get_attribute("class"):
                break
            next_button.click()
            time.sleep(2)  # Wait for the next page to load
            last_page_number += 1
            save_last_page(language, planned, last_page_number)
        except Exception as e:
            logging.error(f"Error navigating to next page: {e}")
            break

        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for language in Language:
        parse_all_pages(EventType.ELECTRICITY, planned=False, language=language)

    driver.quit()
