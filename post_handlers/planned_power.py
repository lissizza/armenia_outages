import aiohttp
import json
import logging

import openai
from utils import escape_markdown_v2, get_translation
from models import Language, PostType
from orm import get_or_create_area, save_post_to_db


logger = logging.getLogger(__name__)
translations = get_translation()


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


async def generate_planned_power_post(session, parsed_event, original_event_id):
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
            title = f"⚡️ {_('Scheduled power outage')} ⚡️"

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
                post_type=PostType.PLANNED_POWER,
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
