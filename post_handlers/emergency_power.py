import logging
from sqlalchemy import String, func, select, update
from utils import escape_markdown_v2, get_translation, natural_sort_key
from models import Event, EventType, PostType
from orm import get_or_create_area, save_post_to_db

logger = logging.getLogger(__name__)
translations = get_translation()


def generate_house_numbers_section(house_numbers, translate):
    """
    Helper function to generate and sort the house numbers section using natural sorting.
    """
    _ = translate
    if house_numbers:
        house_numbers_list = [
            hn.strip() for hn in house_numbers.split(",") if hn.strip()
        ]
        sorted_house_numbers = sorted(house_numbers_list, key=natural_sort_key)
        house_numbers = escape_markdown_v2(", ".join(sorted_house_numbers)).strip()

        return _("House Numbers: {}\n\n").format(house_numbers)
    return ""


async def generate_emergency_power_posts(session):
    try:
        grouped_events = await session.execute(
            select(
                Event.start_time,
                Event.area,
                Event.district,
                Event.language,
                Event.event_type,
                func.string_agg(func.cast(Event.id, String), ",").label("event_ids"),
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
        )
        grouped_events = grouped_events.all()

        logger.info(
            f"Found {len(grouped_events)} grouped unprocessed emergency power events."
        )

        posts_by_area_and_time = {}

        for group in grouped_events:
            event_ids = [int(event_id) for event_id in group.event_ids.split(",")]
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

            title = f"⚡️ {_('Emergency power outage')} ⚡️"

            formatted_area = f"*{escape_markdown_v2(area.strip())}*" if area else ""
            formatted_time = (
                f"*{escape_markdown_v2(start_time.strip())}*" if start_time else ""
            )

            post_text = f"*{title}*\n\n{formatted_area}\n{formatted_time}\n\n"
            all_event_ids = []

            sorted_events = sorted(events_group, key=lambda e: e["district"] or "")

            for event in sorted_events:
                formatted_district = (
                    f"{escape_markdown_v2(event['district'].strip())}\n"
                    if event["district"]
                    else ""
                )
                formatted_house_numbers = generate_house_numbers_section(
                    event["house_numbers"], _
                )
                event_message = f"{formatted_district}{formatted_house_numbers}\n"

                if len(post_text) + len(event_message) > 4096:
                    await save_post_to_db(
                        session,
                        PostType.EMERGENCY_POWER,
                        post_text,
                        all_event_ids,
                        language,
                        db_area,
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
                    session,
                    PostType.EMERGENCY_POWER,
                    post_text,
                    all_event_ids,
                    language,
                    db_area,
                )

            await session.execute(
                update(Event)
                .where(Event.id.in_(all_event_ids))
                .values(processed=True)
                .execution_options(synchronize_session=False)
            )

        await session.commit()
        logger.info("All posts have been saved to the database.")

    except Exception as e:
        await session.rollback()
        logger.error(f"Error while processing events and generating posts: {e}")
        raise
