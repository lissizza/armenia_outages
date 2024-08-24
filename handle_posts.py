from datetime import datetime
import gettext
import logging
import json
import os
from sqlite3 import IntegrityError
import openai
from sqlalchemy import func
from utils import escape_markdown_v2, translate_text
from models import Event, EventType, Language, Post
from db import Session

logger = logging.getLogger(__name__)


# Translation files setup
locales_dir = os.path.join(os.path.dirname(__file__), "locales")
translations = {}

for lang in Language:
    try:
        translation = gettext.translation(
            "messages", localedir=locales_dir, languages=[lang.value[0]]
        )
        translation.install()
        translations[lang.name] = translation.gettext
    except Exception as e:
        logger.error(f"Error loading translation for {lang.value[0]}: {e}")


def save_post_to_db(session, text, event_ids, language):
    """Save a generated post to the database with multiple event_ids."""
    events = session.query(Event).filter(Event.id.in_(event_ids)).all()
    post = Post(
        language=language,
        text=text,
        creation_time=datetime.now(),
        posted_time=None,
        events=events,
    )
    session.add(post)
    logger.debug(f"Post saved to the database: {text[:60]}...")


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


def generate_message(event):
    """Function to generate a message from a processed event."""
    _ = translations[event.language.name]

    title = generate_title(event.event_type, event.planned, event.language)
    title = f"*{escape_markdown_v2(title)}*\n"
    details = ""
    if event.area:
        details += f"*{escape_markdown_v2(event.area)}*\n"
    if event.start_time:
        details += f"*{escape_markdown_v2(event.start_time)}*\n"
    if event.district:
        details += f"{escape_markdown_v2(event.district)}\n"

    details += generate_house_numbers_section(event.house_numbers, _)

    if event.text:
        details += _("Details: {}\n").format(escape_markdown_v2(event.text))

    message_info = {"event_ids": [event.id], "text": f"{title}{details}"}

    return message_info


def generate_emergency_power_posts():
    session = Session()

    try:
        grouped_events = (
            session.query(
                Event.start_time,
                Event.area,
                Event.district,
                Event.language,
                Event.event_type,
                func.group_concat(Event.id).label("event_ids"),
                func.group_concat(Event.house_number, ", ").label("house_numbers"),
            )
            .filter(
                Event.processed == 0,
                Event.event_type == EventType.POWER,
                Event.planned == 0,
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
        )

        logger.info(
            f"Found {len(grouped_events)} grouped unprocessed emergency power events."
        )

        # group events for posts by area and start_time
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

        # make posts
        for (
            area,
            start_time,
            language,
        ), events_group in posts_by_area_and_time.items():
            _ = translations[language.name]

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
                    save_post_to_db(session, post_text, all_event_ids, language)
                    post_text = (
                        f"*{title}*\n{formatted_area}\n{formatted_time}\n"
                        + event_message
                    )
                    all_event_ids = event["event_ids"]
                else:
                    post_text += event_message
                    all_event_ids.extend(event["event_ids"])

            if post_text:
                save_post_to_db(session, post_text, all_event_ids, language)

            session.query(Event).filter(Event.id.in_(all_event_ids)).update(
                {"processed": True}, synchronize_session=False
            )

        session.commit()
        logger.info("All posts have been saved to the database.")

    except Exception as e:
        session.rollback()
        logger.error(f"Error while processing events and generating posts: {e}")
    finally:
        session.close()


def parse_planned_power_event(text):
    logger.debug("Sending text to OpenAI for parsing.")

    prompt = """
Please parse the following Armenian text into structured data and return the result as a JSON object. 
For each event, extract the following information:

- Location: the area where the outage will occur (city, region, village, etc.)
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
        "location": "Երևան",
        "start_time": "22.08.2024 10:00",
        "end_time": "22.08.2024 16:00",
        "text": "Ֆրունզեի փ․\nՕբյեկտներ: 4/1, 6, 6/1, 6/2 շենքեր և հարակից ոչ բնակիչ- բաժանորդներ"
    },
        {
        "language": "RU",
        "location": "Ереван",
        "start_time": "22.08.2024 10:00",
        "end_time": "22.08.2024 16:00",
        "text": "ул. Фрунзе\nОбъекты: дома 4/1, 6, 6/1, 6/2 и прилегающие абоненты не являющиеся жильцами"
    },
        {
        "language": "EN",
        "location": "Yerevan",
        "start_time": "22.08.2024 10:00",
        "end_time": "22.08.2024 16:00",
        "text": "Frunze St.\nObjects: buildings 4/1, 6, 6/1, 6/2 and adjacent non-dweller customers"
    },
    {
        "language": "HY",
        "location": "Երևան",
        "start_time": "22.08.2024 11:00",
        "end_time": "22.08.2024 16:00",
        "text": "Նուբարաշեն Բ թաղամաս, Նորք Մարաշ՝ Նորքի 17 փողոց 1-ին նրբանցք\nՕբյեկտներ: 24/1, 31 առանձնատներ\nԴավիթ Բեկի փ. 97/26, 97/23 առանձնատներ, Դավիթ Բեկի փ. 103/4 հասարակական շինություն և հարակից ոչ բնակիչ- բաժանորդներ"
    },
    {
        "language": "RU",
        "location": "Ереван",
        "start_time": "22.08.2024 11:00",
        "end_time": "22.08.2024 16:00",
        "text": "Нубарашен Б квартал, Норк Мараш, Норк 17-я улица, 1-й переулок\nОбъекты: дома 24/1, 31\nул. Давид Бек 97/26, 97/23 и прилегающие абоненты не являющиеся жильцами"
    },
    {
        "language": "EN",
        "location": "Yerevan",
        "start_time": "22.08.2024 11:00",
        "end_time": "22.08.2024 16:00",
        "text": "Nubarashen B District, Nork Marash, Nork 17th Street, 1st Lane\nObjects: buildings 24/1, 31\nDavid Bek St. 97/26, 97/23, 103/4 and adjacent non-dweller customers"
    }
]

Now, please parse the following text:
{text}
"""

    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=1000,
        temperature=0.2,
    )

    parsed_data = response.choices[0].text.strip()
    logger.debug(f"Received parsed data: {parsed_data}")

    return parsed_data


def generate_planned_power_post(parsed_event, original_event_id):
    session = Session()

    logger.debug(f"Processing parsed event: {parsed_event}")

    try:
        event_data_list = json.loads(parsed_event)
        logger.debug(f"Event data parsed as JSON: {event_data_list}")

        for event_data in event_data_list:
            start_time = event_data["start_time"]
            end_time = event_data["end_time"]
            location = event_data["location"]
            text = event_data["text"]
            language = event_data["language"]

            _ = translations[language.name]
            title = _("Scheduled power outage")

            try:
                lang_enum = Language[language]
            except KeyError:
                logger.error(f"Unknown language code: {language}")
                continue

            escaped_location = escape_markdown_v2(location)
            escaped_time = escape_markdown_v2(f"{start_time} - {end_time}")
            escaped_text = escape_markdown_v2(text)

            post_text = f"**{title}**\n**{escaped_location}**\n**{escaped_time}**\n\n{escaped_text}"
            save_post_to_db(session, post_text, [original_event_id], lang_enum)

        session.commit()
        logger.info("Posts have been committed to the database.")

    except Exception as e:
        logger.error(f"Error while processing parsed event: {e}")
        session.rollback()
    finally:
        session.close()


def generate_water_posts():
    """
    Generate posts for water events by translating them to RU and EN and creating posts directly.
    Marks the original events as processed.
    """
    session = Session()
    unprocessed_water_events = (
        session.query(Event)
        .filter(
            Event.processed == 0,
            Event.event_type == EventType.WATER,
            Event.language == Language.HY,
        )
        .all()
    )

    for event in unprocessed_water_events:
        translation_ru, translation_en = translate_text(event.text)
        google_translations = [
            (Language.HY, event.text),
            (Language.RU, translation_ru),
            (Language.EN, translation_en),
        ]

        try:
            for language, text in google_translations:
                _ = translations[language.name]
                title = (
                    _("Scheduled water outage")
                    if event.planned
                    else _("Emergency water outage")
                )
                escaped_text = escape_markdown_v2(text)
                post_text = f"{title}\n{escaped_text}"

                post = Post(
                    language=language,
                    text=post_text,
                    creation_time=datetime.now(),
                    posted_time=None,
                    events=[event],
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
