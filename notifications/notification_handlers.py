from datetime import datetime
import logging
from models import EventType, Event, Notification, PostType, Subscription


logger = logging.getLogger(__name__)


async def create_notifications_for_subscribers(session) -> None:
    logger.info("Generating notifications for subscribers...")

    subscriptions = session.query(Subscription).all()

    for subscription in subscriptions:
        events = session.query(Event).filter(Event.area == subscription.area.name).all()

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

    session.commit()
