import hashlib


def compute_hash(
    event_type, area, district, house_number, start_time, language, planned
):
    hash_input = f"{event_type}{area}{district}{house_number}{start_time}{language}{planned}".encode(
        "utf-8"
    )
    return hashlib.md5(hash_input).hexdigest()
