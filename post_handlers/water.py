from datetime import datetime
import logging
import re
from models import Area, Event, EventType, Language, PostType
from orm import save_post_to_db
from utils import escape_markdown_v2, get_translation, normalize_text, translate_text
from sqlite3 import IntegrityError
from sqlalchemy.future import select

logger = logging.getLogger(__name__)
translations = get_translation()


async def find_area(session, header, language):
    """
    Find the area name in the given header text using the language-specific area names.
    """
    normalized_header = normalize_text(header)
    all_areas = await session.execute(select(Area).filter_by(language=language))
    all_areas = all_areas.scalars().all()

    for area in all_areas:
        if area.name.upper() in normalized_header:
            return area


def extract_date_time(text):
    """
    Extracts date and time from the given text using regex and returns them in the required format.
    """
    # Regex to find date (e.g., օգոստոսի 31-ին)
    date_pattern = r"(հունվարի|փետրվարի|մարտի|ապրիլի|մայիսի|հունիսի|հուլիսի|օգոստոսի|սեպտեմբերի|հոկտեմբերի|նոյեմբերի|դեկտեմբերի) (\d{1,2})"
    month_map = {
        "հունվարի": "01",
        "փետրվարի": "02",
        "մարտի": "03",
        "ապրիլի": "04",
        "մայիսի": "05",
        "հունիսի": "06",
        "հուլիսի": "07",
        "օգոստոսի": "08",
        "սեպտեմբերի": "09",
        "հոկտեմբերի": "10",
        "նոյեմբերի": "11",
        "դեկտեմբերի": "12",
    }

    # Regex to find time range (e.g., 13:00-17:00)
    time_pattern = r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})"

    # Find matches in the text
    date_match = re.search(date_pattern, text)
    time_match = re.search(time_pattern, text)

    if date_match:
        # Extract the month and day from the match
        month_name = date_match.group(1)
        day = date_match.group(2).zfill(2)  # Ensure day is always two digits
        month = month_map.get(month_name)

        # Use the current year
        current_year = datetime.now().year

        # Format the date as DD.MM.YYYY
        formatted_date = f"{day}.{month}.{current_year}"
    else:
        formatted_date = None

    if time_match:
        # Extract start and end times
        start_time = time_match.group(1)
        end_time = time_match.group(2)

        # Combine date and time
        if formatted_date:
            formatted_date_time = f"{formatted_date} {start_time}-{end_time}"
        else:
            formatted_date_time = None
    else:
        formatted_date_time = None

    return formatted_date_time


async def generate_water_posts(session):
    unprocessed_water_events = await session.execute(
        select(Event).filter(
            Event.processed.is_(False),
            Event.event_type == EventType.WATER,
            Event.language == Language.HY,
        )
    )
    unprocessed_water_events = unprocessed_water_events.scalars().all()

    for event in unprocessed_water_events:
        translation_ru, translation_en = await translate_text(event.text)
        google_translations = [
            (Language.HY, event.text),
            (Language.RU, translation_ru),
            (Language.EN, translation_en),
        ]

        try:
            for language, content in google_translations:
                header, text = (
                    content.split("\n\n", 1) if "\n\n" in content else (content, "")
                )
                area = await find_area(session, header, language)

                if area:
                    logger.info(
                        f"Area matched: {area.name} for event {event.id} and language {language}"
                    )
                else:
                    logger.warning(
                        f"No area matched for event {event.id} and language {language}"
                    )

                _ = translations[language.name]
                title = (
                    f"💧 {_('Scheduled water outage')} 💧"
                    if event.planned
                    else f"💧 {_('Emergency water outage')} 💧"
                )

                area_text = f"*{escape_markdown_v2(area.name)}*\n" if area else ""
                formatted_date_time = extract_date_time(event.text)
                date_time_text = (
                    f"*{escape_markdown_v2(formatted_date_time)}*\n"
                    if formatted_date_time
                    else ""
                )
                escaped_header = escape_markdown_v2(header)
                escaped_text = escape_markdown_v2(text)
                post_text = f"*{title}*\n\n{area_text}{date_time_text}\n{escaped_header}\n\n{escaped_text}"

                await save_post_to_db(
                    session,
                    post_type=(
                        PostType.SCHEDULED_WATER
                        if event.planned
                        else PostType.EMERGENCY_WATER
                    ),
                    text=post_text,
                    event_ids=[event.id],
                    language=language,
                    area=area,
                )

            event.processed = True
            await session.commit()

        except IntegrityError as e:
            await session.rollback()
            logger.error(
                f"Failed to insert water event {event.id} due to IntegrityError: {e}"
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to process water event {event.id}: {e}")
            raise
