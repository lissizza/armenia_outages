import hashlib
from enum import Enum


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
