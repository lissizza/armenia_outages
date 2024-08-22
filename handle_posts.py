from datetime import datetime
import gettext
import logging
import json
import os
import openai
from utils import escape_markdown_v2
from models import EventType, Language, Post, ProcessedEvent
from db import Session
from config import CHANNEL_ID_AM, CHANNEL_ID_EN, CHANNEL_ID_RU, REDIS_URL
import redis

logger = logging.getLogger(__name__)
redis_client = redis.StrictRedis.from_url(REDIS_URL)


# Translation files setup
locales_dir = os.path.join(os.path.dirname(__file__), "locales")

translation_ru = gettext.translation("messages", locales_dir, languages=["ru"])
translation_ru.install()
ru = translation_ru.gettext

translation_en = gettext.translation("messages", locales_dir, languages=["en"])
translation_en.install()
en = translation_en.gettext

translations = {
    "ru": ru,
    "en": en,
}


def save_post_to_db(session, text, event_ids, language):
    """Save a generated post to the database with multiple event_ids."""
    post = Post(
        language=language.value,
        text=text,
        creation_time=datetime.now(),
        posted_time=None,
        event_ids=event_ids,
    )
    session.add(post)
    logger.debug(f"Post saved to the database: {text[:60]}...")


def get_channel_id(language):
    if language == Language.AM:
        return CHANNEL_ID_AM
    elif language == Language.RU:
        return CHANNEL_ID_RU
    elif language == Language.EN:
        return CHANNEL_ID_EN
    return None


def generate_title(event_type, planned, language):
    """Generate the title for a message based on the event type and language."""
    translation = translations[language.value[0]]
    translation.install()
    _ = translation.gettext

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
    lang_code = event.language.value[0]
    translation = translations[lang_code]
    translation.install()
    _ = translation.gettext

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
    """Generate grouped posts by area and start_time from processed events and save them to the database."""
    session = Session()

    try:
        for language in Language:
            emergency_events = (
                session.query(ProcessedEvent)
                .filter_by(
                    sent=False,
                    language=language,
                    event_type=EventType.POWER,
                    planned=False,
                )
                .order_by(ProcessedEvent.start_time)
                .all()
            )

            if not emergency_events:
                continue

            first_event = emergency_events[0]
            lang_code = first_event.language.value[0]
            _ = translations[lang_code]

            title = _("Emergency power outage")

            grouped_events = {}
            for event in emergency_events:
                group_key = (event.area, event.start_time)
                if group_key not in grouped_events:
                    grouped_events[group_key] = []
                grouped_events[group_key].append(event)

            for (area, start_time), events_group in grouped_events.items():
                formatted_area = f"*{escape_markdown_v2(area.strip())}*" if area else ""
                formatted_time = (
                    f"*{escape_markdown_v2(start_time.strip())}*" if start_time else ""
                )

                post_text = f"*{title}*\n{formatted_area}\n{formatted_time}\n"
                event_ids = []

                sorted_events = sorted(events_group, key=lambda e: e.district or "")

                for event in sorted_events:
                    if event.district:
                        formatted_district = escape_markdown_v2(event.district.strip())
                        formatted_house_numbers = generate_house_numbers_section(
                            escape_markdown_v2(event.house_numbers), _
                        ).strip()
                        event_message = (
                            f"{formatted_district}\n{formatted_house_numbers}\n\n"
                        )
                    else:
                        formatted_house_numbers = generate_house_numbers_section(
                            escape_markdown_v2(event.house_numbers), _
                        ).strip()
                        event_message = f"{formatted_house_numbers}\n\n"

                    if len(post_text) + len(event_message) > 4096:
                        save_post_to_db(
                            session, post_text, event_ids, events_group[0].language
                        )
                        post_text = (
                            f"*{title}*\n{formatted_area}\n{formatted_time}\n"
                            + event_message
                        )
                        event_ids = [event.id]
                    else:
                        post_text += event_message
                        event_ids.append(event.id)

                if post_text:
                    save_post_to_db(
                        session, post_text, event_ids, events_group[0].language
                    )

        session.commit()
        logger.info("All posts have been saved to the database.")

    except Exception as e:
        session.rollback()
        logger.error(f"Error while generating and saving posts: {e}")
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

        title = _("Scheduled power outage")

        for event_data in event_data_list:
            start_time = event_data["start_time"]
            end_time = event_data["end_time"]
            location = event_data["location"]
            text = event_data["text"]
            language = event_data["language"]

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
