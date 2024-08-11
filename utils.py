import hashlib
from enum import Enum
from deep_translator import GoogleTranslator

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
