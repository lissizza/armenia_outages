import pytest
from datetime import datetime, timedelta
from models import Event, EventType, Language, Post, Area, post_event_association
from handle_posts import generate_emergency_power_posts
from utils import escape_markdown_v2


@pytest.mark.asyncio
async def test_generate_emergency_power_posts(test_session):
    area_name = "Test Area"
    start_time = (datetime.now() - timedelta(hours=1)).strftime("%d.%m.%Y %H:%M")
    escaped_start_time = escape_markdown_v2(start_time)
    event_type = EventType.POWER
    language = Language.EN

    test_area = Area(name=area_name, language=language)
    test_session.add(test_area)
    test_session.commit()

    event1 = Event(
        event_type=event_type,
        language=language,
        area=area_name,
        district="Test District",
        house_number="1",
        start_time=start_time,
        end_time=None,
        planned=False,
        processed=False,
        timestamp=datetime.now(),
        hash="testhash1",
    )

    event2 = Event(
        event_type=event_type,
        language=language,
        area=area_name,
        district="Test District",
        house_number="2,3",
        start_time=start_time,
        end_time=None,
        planned=False,
        processed=False,
        timestamp=datetime.now(),
        hash="testhash2",
    )

    event3 = Event(
        event_type=event_type,
        language=language,
        area=area_name,
        district="Another District",
        house_number="4,5",
        start_time=start_time,
        end_time=None,
        planned=False,
        processed=False,
        timestamp=datetime.now(),
        hash="testhash3",
    )

    test_session.add_all([event1, event2, event3])
    test_session.commit()

    assert test_session.query(Event).count() == 3

    await generate_emergency_power_posts(test_session)

    posts = test_session.query(Post).all()

    # Отладочный вывод
    print("\nGenerated Posts:\n", posts)

    assert len(posts) == 1

    post_text = posts[0].text
    print("\nGenerated Post:\n", post_text)

    assert post_text.count("*⚡️ Emergency power outage ⚡️*\n\n") == 1
    assert post_text.count(f"*{area_name}*\n") == 1
    assert post_text.count(f"*{escaped_start_time}*\n\n") == 1
    assert post_text.count("Test District\n") == 1
    assert post_text.count("Another District\n") == 1
    assert post_text.count("1, 2, 3\n") == 1
    assert post_text.count("4, 5\n\n") == 1

    test_session.query(post_event_association).delete()
    test_session.query(Post).delete()
    test_session.query(Event).delete()
    test_session.query(Area).delete()
    test_session.commit()
    test_session.close()
