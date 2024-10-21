import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from models import Event, EventType, Language
from config import POWER_OUTAGE_URL
import re
from utils import compute_hash, normalize_and_translate_value
from sqlalchemy.future import select

logger = logging.getLogger(__name__)


def split_address(address):
    parts = address.split(",")
    if len(parts) == 1:
        return parts[0].strip(), None, None  # Only area, no district or house number

    # Separate area and right part after the first comma
    area = parts[0].strip()
    right_part = ",".join(parts[1:]).strip()  # Join the rest in case of multiple commas

    # Regular expression to check for valid house number patterns
    house_number_pattern = r"^[\dA-ZА-Яа-ֆ/\\\-.,]*\d+[\dA-ZА-Яа-ֆ/\\\-.,]*$"
    number_letter_pattern = r"^\d+ [Ա-Ֆա-ֆ]$"

    # Additional check if the right part could be a house number with space and single letter
    if re.match(number_letter_pattern, right_part):
        return area, None, right_part  # Only area and house number, no district

    # Check if the entire right part could be a house number
    if re.match(house_number_pattern, right_part) and not (
        " " in right_part and not re.match(number_letter_pattern, right_part)
    ):
        return area, None, right_part  # Only area and house number, no district

    # If the entire right part is not a house number, try to split by the last space
    last_space_index = right_part.rfind(" ")

    if last_space_index != -1:
        # Check potential house number after the last space
        potential_house_number = right_part[last_space_index + 1 :].strip()
        district = right_part[:last_space_index].strip()

        # Check if potential house number is a valid house number
        if re.match(house_number_pattern, potential_house_number):
            # Additional check for cases with number and single Armenian letter
            if " " in potential_house_number and not re.match(
                number_letter_pattern, potential_house_number
            ):
                # Continue checking for the case where there might be another space within the district
                pass
            else:
                return area, district, potential_house_number

        # Check for the presence of a second-to-last space
        second_last_space_index = right_part[:last_space_index].rfind(" ")
        if second_last_space_index != -1:
            potential_house_number = right_part[second_last_space_index + 1 :].strip()
            district = right_part[:second_last_space_index].strip()
            if re.match(number_letter_pattern, potential_house_number):
                return area, district, potential_house_number
            else:
                return area, right_part, None
        else:
            # If there is no second last space, treat the whole right part as district
            return area, right_part, None
    else:
        # No spaces in the right part; consider it entirely as district
        return area, right_part, None


def filter_by_date(event_date_str):
    try:
        event_date = datetime.strptime(event_date_str, "%d.%m.%Y %H:%M")
        current_date = datetime.now()
        return current_date - event_date <= timedelta(days=1)
    except ValueError:
        return False


async def fetch_page(url):
    """
    Fetch the page content with JavaScript disabled.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"Failed to retrieve data from {url}: {response.status}")
                return None

            html = await response.text()
            return html


async def parse_emergency_power_events(db_session):
    """
    Asynchronously parse power outages data for all supported languages.
    """
    for language in Language:
        logger.info(f"Parsing emergency power updates for language: {language.name}")

        try:
            html = await fetch_page(POWER_OUTAGE_URL.format(lang=language.code))
            if not html:
                logger.error(
                    f"No HTML content returned for {language.name}. Skipping..."
                )
                continue

            soup = BeautifulSoup(html, "html.parser")
            data = await parse_table(soup)

            new_records_count = 0

            for event in data:
                area, district, house_numbers = split_address(event[1])
                start_time = normalize_and_translate_value(event[0])
                area = normalize_and_translate_value(area, language.text)
                district = normalize_and_translate_value(district, language.text)
                house_numbers = normalize_and_translate_value(
                    house_numbers, language.text
                )

                if not filter_by_date(start_time):
                    continue

                event_hash = compute_hash(
                    EventType.POWER,
                    area,
                    district,
                    house_numbers,
                    start_time,
                    language,
                    False,
                )

                result = await db_session.execute(
                    select(Event).filter_by(hash=event_hash)
                )
                existing_event = result.scalars().first()

                if existing_event:
                    continue

                new_event = Event(
                    event_type=EventType.POWER,
                    area=area,
                    district=district,
                    house_number=house_numbers,
                    start_time=start_time,
                    end_time=None,
                    language=language,
                    planned=False,
                    hash=event_hash,
                    timestamp=datetime.now(),
                )
                db_session.add(new_event)
                new_records_count += 1

            await db_session.commit()

            logger.info(
                f"Added {new_records_count} new records to the database for language {language.name}."
            )

        except Exception as e:
            logger.error(f"Error during parsing: {e}")


async def parse_table(soup):
    """
    Parses the table from the provided BeautifulSoup object.
    """
    try:
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

        logger.info(f"Parsed {len(data)} rows from the table.")

        return data
    except Exception as e:
        logger.error(f"Error while parsing the table: {e}")
        return []


if __name__ == "__main__":
    from db import session_scope

    async def main():
        async with session_scope() as db_session:
            await parse_emergency_power_events(db_session)

    asyncio.run(main())
