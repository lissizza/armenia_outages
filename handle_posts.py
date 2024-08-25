import aiohttp
import asyncio
from datetime import datetime
import logging
import json
from sqlite3 import IntegrityError
import openai
from sqlalchemy import String, func
from utils import escape_markdown_v2, get_translation, translate_text
from models import Area, Event, EventType, Language, Post
from db import Session
from sqlalchemy.orm import Session as SQLAlchemySession

logger = logging.getLogger(__name__)
translations = get_translation()


async def save_post_to_db(session, text, event_ids, language, area):
    """Save a generated post to the database with multiple event_ids asynchronously."""
    loop = asyncio.get_event_loop()
    events = await loop.run_in_executor(
        None, lambda: session.query(Event).filter(Event.id.in_(event_ids)).all()
    )

    post = Post(
        language=language,
        area=area,
        text=text,
        creation_time=datetime.now(),
        posted_time=None,
        events=events,
    )

    await loop.run_in_executor(None, session.add, post)
    logger.debug(f"Post saved to the database: {text[:60]}...")


async def clean_area_name(raw_name):
    prefixes = [
        "г.",
        "город",
        "с.",
        "деревня",
        "пгт",
        "поселок",
        "Ք.",
        "Քաղաք",
        "Գ.",
        "Գյուղ",
        "Վ.",
        "С.",
        "Г.",
        "V.",
        "V",
        "Ս.",
    ]

    for prefix in prefixes:
        if raw_name.startswith(prefix):
            raw_name = raw_name[len(prefix) :].strip()
            break
        elif "." in raw_name:
            raw_name = raw_name.split(".")[1].strip()
            break

    cleaned_name = raw_name.split("(")[0].strip()

    return cleaned_name.capitalize()


async def get_or_create_area(
    session: SQLAlchemySession, area_name: str, language: Language
) -> Area:
    """
    Retrieves an existing Area by name and language, or creates it if it doesn't exist.

    :param session: SQLAlchemy session.
    :param area_name: The name of the area.
    :param language: The language of the area.
    :return: The Area instance.
    """
    area_name = await clean_area_name(area_name)
    loop = asyncio.get_event_loop()

    # Check if the area already exists
    area = await loop.run_in_executor(
        None,
        lambda: session.query(Area)
        .filter_by(name=area_name, language=language)
        .first(),
    )

    # If the area doesn't exist, create it
    if not area:
        area = Area(name=area_name, language=language)
        session.add(area)
        await loop.run_in_executor(None, session.commit)

    return area


def generate_title(event_type, planned, language):
    """Generate the title for a message based on the event type and language."""
    _ = translations[language.name]

    if event_type == EventType.WATER:
        title = _("Scheduled water outage") if planned else _("Emergency water outage")
    elif event_type == EventType.GAS:
        title = _("Scheduled gas outage") if planned else _("Emergency gas outage")

    return title


def generate_house_numbers_section(house_numbers, _):
    """Helper function to generate the house numbers section."""
    if house_numbers:
        house_numbers = ", ".join(
            [num for num in house_numbers.split(", ") if num.strip()]
        )
        return _("House Numbers: {}\n").format(house_numbers)
    return ""


async def generate_emergency_power_posts():
    session = Session()

    try:
        loop = asyncio.get_event_loop()

        grouped_events = await loop.run_in_executor(
            None,
            lambda: (
                session.query(
                    Event.start_time,
                    Event.area,
                    Event.district,
                    Event.language,
                    Event.event_type,
                    func.string_agg(func.cast(Event.id, String), ",").label(
                        "event_ids"
                    ),
                    func.string_agg(Event.house_number, ", ").label("house_numbers"),
                )
                .filter(
                    Event.processed.is_(False),
                    Event.event_type == EventType.POWER,
                    Event.planned.is_(False),
                    (Event.area.isnot(None))
                    | (Event.district.isnot(None))
                    | (Event.house_number.isnot(None)),
                )
                .group_by(
                    Event.start_time,
                    Event.area,
                    Event.district,
                    Event.language,
                    Event.event_type,
                )
                .all()
            ),
        )

        logger.info(
            f"Found {len(grouped_events)} grouped unprocessed emergency power events."
        )

        posts_by_area_and_time = {}

        for group in grouped_events:
            event_ids = group.event_ids.split(",")
            logger.info(f"Processing group with event IDs: {event_ids}")

            group_key = (group.area, group.start_time, group.language)
            if group_key not in posts_by_area_and_time:
                posts_by_area_and_time[group_key] = []

            posts_by_area_and_time[group_key].append(
                {
                    "district": group.district,
                    "house_numbers": group.house_numbers,
                    "event_type": group.event_type,
                    "event_ids": event_ids,
                }
            )

        for (
            area,
            start_time,
            language,
        ), events_group in posts_by_area_and_time.items():
            _ = translations[language.name]

            db_area = await get_or_create_area(session, area, language)

            title = _("Emergency power outage")

            formatted_area = f"*{escape_markdown_v2(area.strip())}*" if area else ""
            formatted_time = (
                f"*{escape_markdown_v2(start_time.strip())}*" if start_time else ""
            )

            post_text = f"*{title}*\n{formatted_area}\n{formatted_time}\n"
            all_event_ids = []

            sorted_events = sorted(events_group, key=lambda e: e["district"] or "")

            for event in sorted_events:
                if event["district"]:
                    formatted_district = escape_markdown_v2(event["district"].strip())
                    formatted_house_numbers = generate_house_numbers_section(
                        escape_markdown_v2(event["house_numbers"]), _
                    ).strip()
                    event_message = (
                        f"{formatted_district}\n{formatted_house_numbers}\n\n"
                    )
                else:
                    formatted_house_numbers = generate_house_numbers_section(
                        escape_markdown_v2(event["house_numbers"]), _
                    ).strip()
                    event_message = f"{formatted_house_numbers}\n\n"

                if len(post_text) + len(event_message) > 4096:
                    await save_post_to_db(
                        session, post_text, all_event_ids, language, db_area
                    )
                    post_text = (
                        f"*{title}*\n{formatted_area}\n{formatted_time}\n"
                        + event_message
                    )
                    all_event_ids = event["event_ids"]
                else:
                    post_text += event_message
                    all_event_ids.extend(event["event_ids"])

            if post_text:
                await save_post_to_db(
                    session, post_text, all_event_ids, language, db_area
                )

            await loop.run_in_executor(
                None,
                lambda: session.query(Event)
                .filter(Event.id.in_(all_event_ids))
                .update({"processed": True}, synchronize_session=False),
            )

        session.commit()
        logger.info("All posts have been saved to the database.")

    except Exception as e:
        session.rollback()
        logger.error(f"Error while processing events and generating posts: {e}")
    finally:
        session.close()


async def parse_planned_power_event(content):
    logger.debug("Sending text to OpenAI for parsing.")

    prompt = """
Please parse the following Armenian text into structured data and return the result as a JSON object. 
For each event, extract the following information:

- Area: the area where the outage will occur (city, region, village, etc.)
- Start Time: combine the date and start time into the format 'DD.MM.YYYY HH:MM'
- End Time: combine the date and end time into the format 'DD.MM.YYYY HH:MM'
- Language: the language of the text (EN for English, RU for Russian, HY for Armenian)
- Text: generate a structured text where:
  - Streets or Areas are grouped with the label "ул. <Street Name>" or "<Area Name>" 
(in Armenian for HY, in Russian for RU, and in English for EN)
  - Objects (such as house numbers or named entities) are listed under "Objects:"

For example, given this input:

«Հայաստանի էլեկտրական ցանցեր» փակ բաժնետիրական ընկերությունը տեղեկացնում է, որ օգոստոսի 22-ին պլանային նորոգման 
աշխատանքներ իրականացնելու նպատակով ժամանակավորապես կդադարեցվի հետևյալ հասցեների էլեկտրամատակարարումը`

Երևան քաղաք՝

10։00-16:00 Ֆրունզեի փ․ 4/1, 6, 6/1, 6/2 շենքեր և հարակից ոչ բնակիչ- բաժանորդներ,

11։00-16:00 Նուբարաշեն Բ թաղամաս, Նորք Մարաշ՝ Նորքի 17 փողոց 1-ին նրբանցք 24/1, 31 առանձնատներ, Դավիթ Բեկի փ. 97/26, 
97/23 առանձնատներ, Դավիթ Բեկի փ. 103/4 հասարակական շինություն և հարակից ոչ բնակիչ- բաժանորդներ,"

The output should be:

[
    {
        "language": "HY",
        "area": "Երևան",
        "start_time": "22.08.2024 10:00",
        "end_time": "22.08.2024 16:00",
        "text": "Ֆրունզեի փ․\nՕբյեկտներ: 4/1, 6, 6/1, 6/2 շենքեր և հարակից ոչ բնակիչ- բաժանորդներ"
    },
        {
        "language": "RU",
        "area": "Ереван",
        "start_time": "22.08.2024 10:00",
        "end_time": "22.08.2024 16:00",
        "text": "ул. Фрунзе\nОбъекты: дома 4/1, 6, 6/1, 6/2 и прилегающие абоненты не являющиеся жильцами"
    },
        {
        "language": "EN",
        "area": "Yerevan",
        "start_time": "22.08.2024 10:00",
        "end_time": "22.08.2024 16:00",
        "text": "Frunze St.\nObjects: buildings 4/1, 6, 6/1, 6/2 and adjacent non-dweller customers"
    },
    {
        "language": "HY",
        "area": "Երևան",
        "start_time": "22.08.2024 11:00",
        "end_time": "22.08.2024 16:00",
        "text": "Նուբարաշեն Բ թաղամաս, Նորք Մարաշ՝ Նորքի 17 փողոց 1-ին նրբանցք\nՕբյեկտներ: 24/1, 31 առանձնատներ\nԴավիթ Բեկի փ. 97/26, 97/23 առանձնատներ, Դավիթ Բեկի փ. 103/4 հասարակական շինություն և հարակից ոչ բնակիչ- բաժանորդներ"
    },
    {
        "language": "RU",
        "area": "Ереван",
        "start_time": "22.08.2024 11:00",
        "end_time": "22.08.2024 16:00",
        "text": "Нубарашен Б квартал, Норк Мараш, Норк 17-я улица, 1-й переулок\nОбъекты: дома 24/1, 31\nул. Давид Бек 97/26, 97/23 и прилегающие абоненты не являющиеся жильцами"
    },
    {
        "language": "EN",
        "area": "Yerevan",
        "start_time": "22.08.2024 11:00",
        "end_time": "22.08.2024 16:00",
        "text": "Nubarashen B District, Nork Marash, Nork 17th Street, 1st Lane\nObjects: buildings 24/1, 31\nDavid Bek St. 97/26, 97/23, 103/4 and adjacent non-dweller customers"
    }
]

Now, please parse the following text:
{content}
"""

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.openai.com/v1/completions",
            json={
                "model": "text-davinci-003",
                "prompt": prompt,
                "max_tokens": 1000,
                "temperature": 0.2,
            },
            headers={"Authorization": f"Bearer {openai.api_key}"},
        ) as response:
            if response.status != 200:
                logger.error(f"Failed to get completion from OpenAI: {response.status}")
                return None

            response_data = await response.json()
            parsed_data = response_data["choices"][0]["text"].strip()
            logger.debug(f"Received parsed data: {parsed_data}")
            return parsed_data


async def generate_planned_power_post(parsed_event, original_event_id):
    session = Session()

    logger.debug(f"Processing parsed event: {parsed_event}")

    try:
        event_data_list = json.loads(parsed_event)
        logger.debug(f"Event data parsed as JSON: {event_data_list}")

        for event_data in event_data_list:
            start_time = event_data["start_time"]
            end_time = event_data["end_time"]
            area = event_data["area"]
            text = event_data["text"]
            language = event_data["language"]

            _ = translations[language.name]
            title = _("Scheduled power outage")

            try:
                lang_enum = Language[language]
            except KeyError:
                logger.error(f"Unknown language code: {language}")
                continue

            escaped_area = escape_markdown_v2(area)
            escaped_time = escape_markdown_v2(f"{start_time} - {end_time}")
            escaped_text = escape_markdown_v2(text)

            db_area = await get_or_create_area(session, area, lang_enum)

            post_text = (
                f"**{title}**\n**{escaped_area}**\n**{escaped_time}**\n\n{escaped_text}"
            )
            await save_post_to_db(
                session,
                language=lang_enum,
                area=db_area,
                text=post_text,
                events=[original_event_id],
            )

        session.commit()
        logger.info("Posts have been committed to the database.")

    except Exception as e:
        logger.error(f"Error while processing parsed event: {e}")
        session.rollback()
    finally:
        session.close()


async def generate_water_posts():
    session = Session()
    all_areas = await asyncio.get_event_loop().run_in_executor(
        None, lambda: session.query(Area).all()
    )

    unprocessed_water_events = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: session.query(Event)
        .filter(
            Event.processed.is_(False),
            Event.event_type == EventType.WATER,
            Event.language == Language.HY,
        )
        .all(),
    )

    for event in unprocessed_water_events:
        translation_ru, translation_en = await translate_text(event.text)
        google_translations = [
            (Language.HY, event.text),
            (Language.RU, translation_ru),
            (Language.EN, translation_en),
        ]

        matched_area = None

        try:
            for language, content in google_translations:
                for area in all_areas:
                    if (
                        area.language == language
                        and area.name.lower() in content.lower()
                    ):
                        matched_area = area
                        break
                if matched_area:
                    break

            if matched_area:
                logger.info(f"Area matched: {matched_area.name} for event {event.id}")
            else:
                logger.warning(f"No area matched for event {event.id}")

            for language, content in google_translations:
                _ = translations[language.name]
                title = (
                    _("Scheduled water outage")
                    if event.planned
                    else _("Emergency water outage")
                )
                escaped_text = escape_markdown_v2(content)
                post_text = f"{title}\n{escaped_text}"

                post = Post(
                    language=language,
                    text=post_text,
                    creation_time=datetime.now(),
                    posted_time=None,
                    events=[event],
                    area=matched_area,
                )
                session.add(post)

            session.commit()

            event.processed = True
            session.commit()

        except IntegrityError as e:
            session.rollback()
            logger.error(
                f"Failed to insert water event {event.id} due to IntegrityError: {e}"
            )
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to process water event {event.id}: {e}")

    session.close()
