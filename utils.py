import asyncio
import gettext
import hashlib
from enum import Enum
import logging
import os
import re
import unicodedata
from deep_translator import GoogleTranslator
import requests

from config import CHANNEL_ID_EN, CHANNEL_ID_HY, CHANNEL_ID_RU
from models import Language

logger = logging.getLogger(__name__)

translator_ru = GoogleTranslator(source="auto", target="ru")
translator_en = GoogleTranslator(source="auto", target="en")


async def translate_text(text):
    loop = asyncio.get_event_loop()
    translation_ru = await loop.run_in_executor(None, translator_ru.translate, text)
    translation_en = await loop.run_in_executor(None, translator_en.translate, text)
    return translation_ru, translation_en


def get_translation():
    locales_dir = os.path.join(os.path.dirname(__file__), "locales")
    translations = {}

    for lang in Language:
        try:
            translation = gettext.translation(
                "messages", localedir=locales_dir, languages=[lang.text]
            )
            translation.install()
            translations[lang.name] = translation.gettext
        except Exception as e:
            logger.error(f"Error loading translation for {lang.text}: {e}")

    return translations


def lingva_translate(text, source_lang="hy", target_lang=None):
    """
    Translate text using Lingva Translate API.
    """
    if not target_lang:
        return text

    url = f"https://lingva.ml/api/v1/{source_lang}/{target_lang}/{text}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        translation_data = response.json()
        return translation_data["translation"]
    except Exception as e:
        logger.error(f"Error with Lingva Translate: {e}")
        return text


def normalize_and_translate_value(value, target_language=None):
    """
    Normalize and optionally translate the input value.

    Handles normalization for different types of input (strings, enums) and applies translation
    for strings if a target language is specified.
    """
    # Handle None input
    if value is None:
        return ""

    # Normalize based on type
    if isinstance(value, Enum):
        value = value.name.upper()
    else:
        value = str(value).strip().upper()

    # Apply Unicode normalization to the string
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"\s+", " ", value)  # Replace multiple spaces with a single space

    # Direct corrections for known incorrect translations
    corrections = {
        "ШАРК": "РЯД",
        "SHARQ": "ROW",
        "МИКРОШРДЖАН": "МИКРОРАЙОН",
        "MIKROSHRDJAN": "MICRODISTRICT",
    }

    # Apply corrections if the value is a string and corrections exist for it
    if isinstance(value, str):
        for wrong, correct in corrections.items():
            if wrong in value:
                value = value.replace(wrong, correct)

    # Detect language and translate if needed
    if target_language:
        detected_language = detect_language_by_charset(value)
        logger.debug(f"Detected language: {detected_language}")

        # Translate any remaining untranslated Armenian words
        if (
            detected_language == Language.HY.name.lower()
            and target_language != Language.HY.name.lower()
        ):
            logger.debug(f"Translating {value} from Armenian to {target_language}")
            value = lingva_translate(value, Language.HY.name.lower(), target_language)

    return value


def compute_hash(*args):
    clean_args = [normalize_and_translate_value(arg) if arg else "" for arg in args]
    concatenated = "".join(clean_args)
    return compute_hash_by_text(concatenated)


def compute_hash_by_text(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def escape_markdown_v2(text):
    """
    Replaces all dash variants with a regular hyphen and escapes special characters in the text for correct rendering in MarkdownV2.

    Args:
        text (str): The text to be escaped.

    Returns:
        str: The escaped text ready for MarkdownV2.
    """
    # Replace all dash variants with a regular hyphen
    text = text.replace("—", "-")  # em-dash
    text = text.replace("–", "-")  # en-dash
    text = text.replace("−", "-")  # minus sign (not a hyphen)

    special_characters = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]

    # Replace non-breaking spaces with regular spaces
    text = text.replace("\u00A0", " ")

    # Escape all special characters
    escaped_text = text
    for char in special_characters:
        escaped_text = escaped_text.replace(char, f"\\{char}")

    return escaped_text


def combine_date_time(date_str, time_str):
    """
    Combines date and time into a single string in the format 'DD.MM.YYYY HH:MM'.

    :param date_str: Date in the format 'DD.MM.YYYY'
    :param time_str: Time in the format 'HH:MM'
    :return: Combined date and time string
    """
    return f"{date_str} {time_str}"


def get_channel_id(language):
    channel_mapping = {
        Language.HY: CHANNEL_ID_HY,
        Language.RU: CHANNEL_ID_RU,
        Language.EN: CHANNEL_ID_EN,
    }

    return channel_mapping.get(language)


def natural_sort_key(s):
    """
    Generate a sort key for natural sorting.
    Splits a string into a list of integers and strings, ensuring that numbers are sorted numerically.
    """
    return [
        int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)
    ]


def detect_language_by_charset(text):
    """
    Detects language by checking the character set of the text.
    Returns 'en' for English, 'ru' for Russian, 'hy' for Armenian, or None if undetermined.
    """

    cyrillic_chars = set(
        "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    )
    armenian_chars = set(
        "ԱԲԳԴԵԶԷԸԹԺԻԼԽԾԿՀՁՂՃՄՅՆՇՈՉՊՋՌՍՎՏՐՑՒՓՔՕՖաաբգդեզէըթժիլխծկհձղճմյնշոչպջռսվտրցւփքօֆ"
    )

    text_chars = set(text.replace(" ", ""))

    if text_chars & armenian_chars:
        return Language.HY
    elif text_chars & cyrillic_chars:
        return Language.RU
    elif any("a" <= c <= "z" or "A" <= c <= "Z" for c in text):
        return Language.EN
    else:
        return None
