from datetime import datetime
import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from models import Event, ProcessedEvent, EventType, Language
from db import Session
from utils import translate_text

logger = logging.getLogger(__name__)


def process_emergency_power_events():
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

        for group in grouped_events:
            event_ids = group.event_ids.split(",")
            logger.info(f"Processing group with event IDs: {event_ids}")

            existing_event = (
                session.query(ProcessedEvent)
                .filter_by(
                    start_time=group.start_time,
                    area=group.area,
                    district=group.district,
                    language=group.language,
                    event_type=group.event_type,
                    planned=False,
                )
                .first()
            )

            if existing_event:
                logger.info(
                    f"Updating existing processed event for group with event IDs: {event_ids}"
                )
                existing_house_numbers = list(
                    filter(None, existing_event.house_numbers.split(", "))
                )
                new_house_numbers = list(filter(None, group.house_numbers.split(", ")))

                existing_event.house_numbers = ", ".join(
                    sorted(set(existing_house_numbers + new_house_numbers))
                )
                existing_event.sent = False
                existing_event.timestamp = datetime.now().isoformat()

                session.commit()
            else:
                logger.info(
                    f"Inserting new processed event for group with event IDs: {event_ids}"
                )
                processed_event = ProcessedEvent(
                    start_time=group.start_time,
                    area=group.area,
                    district=group.district,
                    house_numbers=group.house_numbers,
                    language=group.language,
                    event_type=group.event_type,
                    planned=False,
                    sent=False,
                    timestamp=datetime.now().isoformat(),
                )
                session.add(processed_event)
                session.commit()
                logger.info(f"Inserted new processed event with event IDs: {event_ids}")

            session.query(Event).filter(Event.id.in_(event_ids)).update(
                {"processed": True}, synchronize_session=False
            )
            session.commit()

    except Exception as e:
        logger.error(f"Failed to process events: {e}")
        session.rollback()
    finally:
        session.close()


def process_water_events():
    """
    Process water events by directly transferring them from the events table
    to the processed_events table, including translation for RU and EN.
    Marks the original events as processed.
    """
    session = Session()
    unprocessed_water_events = (
        session.query(Event)
        .filter(
            Event.processed == 0,
            Event.event_type == EventType.WATER,
            Event.language == Language.AM,
        )
        .all()
    )

    for event in unprocessed_water_events:
        # Translate the text
        translation_ru, translation_en = translate_text(event.text)

        # Create processed events for all three languages
        processed_event_am = ProcessedEvent(
            start_time=event.start_time,
            area=event.area,
            district=event.district,
            house_numbers=event.house_number,
            language=Language.AM,
            event_type=event.event_type,
            planned=event.planned,
            sent=False,
            timestamp=datetime.now().isoformat(),
            text=event.text,
        )

        processed_event_ru = ProcessedEvent(
            start_time=event.start_time,
            area=event.area,
            district=event.district,
            house_numbers=event.house_number,
            language=Language.RU,
            event_type=event.event_type,
            planned=event.planned,
            sent=False,
            timestamp=datetime.now().isoformat(),
            text=translation_ru,
        )

        processed_event_en = ProcessedEvent(
            start_time=event.start_time,
            area=event.area,
            district=event.district,
            house_numbers=event.house_number,
            language=Language.EN,
            event_type=event.event_type,
            planned=event.planned,
            sent=False,
            timestamp=datetime.now().isoformat(),
            text=translation_en,
        )

        try:
            session.add_all(
                [processed_event_am, processed_event_ru, processed_event_en]
            )
            session.commit()

            event.processed = True
            session.commit()

        except IntegrityError:
            session.rollback()
            logger.error(
                f"Failed to insert water event {event.id} due to IntegrityError"
            )
    session.close()
