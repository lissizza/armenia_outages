from datetime import datetime
import logging
from models import EventType, Event, Notification, PostType, Subscription
from sqlalchemy.future import select

logger = logging.getLogger(__name__)


async def create_notifications_for_subscribers(session) -> None:
    logger.info("Generating notifications for subscribers...")

    result = await session.execute(select(Subscription))
    subscriptions = result.scalars().all()

    for subscription in subscriptions:
        result = await session.execute(
            select(Event).filter(Event.area == subscription.area.name)
        )
        events = result.scalars().all()

        if subscription.keyword:
            events = [
                event
                for event in events
                if (
                    event.event_type == EventType.POWER
                    and event.district
                    and subscription.keyword.lower() in event.district.lower()
                )
                or (
                    event.event_type != EventType.POWER
                    and event.text
                    and subscription.keyword.lower() in event.text.lower()
                )
            ]

        for event in events:
            notification = Notification(
                subscription_id=subscription.id,
                language=subscription.area.language,
                notification_type=PostType[event.event_type.name],
                text=f"Новое событие: {event.text}",
                creation_time=datetime.now(),
            )
            session.add(notification)
            logger.info(
                f"Created notification for subscription ID {subscription.id} for event ID {event.id}"
            )

    await session.commit()
