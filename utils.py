import hashlib
from enum import Enum
from deep_translator import GoogleTranslator

from config import CHANNEL_ID_EN, CHANNEL_ID_HY, CHANNEL_ID_RU
from db import Session
from models import BotUser, Language

translator_ru = GoogleTranslator(source="auto", target="ru")
translator_en = GoogleTranslator(source="auto", target="en")


def translate_text(text):
    translation_ru = translator_ru.translate(text)
    translation_en = translator_en.translate(text)
    return translation_ru, translation_en


def normalize_string(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip().upper()
    elif isinstance(value, Enum):
        return value.name.upper()
    else:
        return str(value).strip().upper()


def compute_hash(*args):
    clean_args = [normalize_string(arg) if arg else "" for arg in args]
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


def get_user_by_telegram_id(telegram_id):
    """
    Fetches the user from the database by Telegram user ID.

    :param telegram_id: Telegram user ID (update.effective_user.id)
    :return: BotUser instance or None if not found
    """
    session = Session()

    user = session.query(BotUser).filter_by(user_id=telegram_id).first()

    session.close()

    return user


def get_channel_id(language):
    channel_mapping = {
        Language.HY: CHANNEL_ID_HY,
        Language.RU: CHANNEL_ID_RU,
        Language.EN: CHANNEL_ID_EN,
    }

    return channel_mapping.get(language)
