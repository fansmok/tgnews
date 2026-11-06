from datetime import datetime
from zoneinfo import ZoneInfo

from newsagent.ads import parse_ad_post, select_ads

MSK = ZoneInfo("Europe/Moscow")


def test_parses_the_channel_schedule_and_ignores_slot_names():
    text = "Реклама сегодня\n11:00\n15:00\n21:40 транса\n"
    posted = datetime(2026, 10, 22, 8, 0, tzinfo=MSK)
    parsed = parse_ad_post(text, posted)
    assert parsed is not None
    assert [item[11:16] for item in parsed["slots"]] == ["11:00", "15:00", "21:40"]
    assert parsed["cancelled"] is False


def test_cancel_post_clears_the_day():
    posted = datetime(2026, 10, 22, 9, 0, tzinfo=MSK)
    earlier = {
        "text": "Реклама сегодня\n11:00\n",
        "message_at": datetime(2026, 10, 22, 7, 0, tzinfo=MSK),
    }
    latest = {"text": "Реклама сегодня\nбез рекламы\n", "message_at": posted}
    assert select_ads([latest, earlier]) == []


def test_tomorrow_header_uses_the_next_date():
    posted = datetime(2026, 10, 22, 18, 0, tzinfo=MSK)
    parsed = parse_ad_post("Реклама завтра\n10:30 слот\n", posted)
    assert parsed["slots"] == ["2026-10-23T10:30:00+03:00"]


def test_broadcast_and_dash_delimiters_are_recognized():
    text = "Реклама сегодня\n11-00\n21-40 трансляция\n"
    posted = datetime(2026, 10, 22, 8, 0, tzinfo=MSK)
    parsed = parse_ad_post(text, posted)
    assert parsed is not None
    assert [item[11:16] for item in parsed["slots"]] == ["11:00", "21:40"]
    items = parsed["items"]
    assert items[0]["kind"] == "regular"
    assert items[1]["kind"] == "broadcast"


def test_webhook_post_overrides_the_older_channel_schedule():
    from newsagent.ads import combine_ad_messages, message_from_webhook

    posted = datetime(2026, 11, 6, 17, 30, tzinfo=MSK)
    channel = [{"text": "Реклама сегодня\n11:00\n", "message_at": datetime(2026, 11, 6, 8, 0, tzinfo=MSK)}]
    incoming = message_from_webhook(
        {"text": "Реклама сегодня\n18:40\n21-10 трансляция\n", "date": "2026-11-06T17:30:00+03:00"},
        posted,
    )
    assert incoming is not None
    assert incoming["message_at"].tzinfo is not None
    merged = combine_ad_messages(channel, [incoming])
    assert [item[11:16] for item in select_ads(merged)] == ["18:40", "21:10"]
    via_unix = message_from_webhook(
        {"channel_post": {"text": "Реклама сегодня\n19:00\n", "date": int(posted.timestamp())}},
        posted,
    )
    assert via_unix["message_at"].astimezone(MSK) == posted


def test_channel_posts_keep_the_clock_time_and_ignore_grid_notes():
    posted = datetime(2026, 11, 6, 9, 0, tzinfo=MSK)
    samples = {
        "...20:45 \n\nВся сетка": "20:45",
        "Реклама сегодня \n\n20:00\n\nВся сетка": "20:00",
        "Реклама сегодня \n\n11:00 \n\nВся сетка": "11:00",
        "Реклама сегодня в этих каналах 👇 \n\nФутбол news \nЛа лига \nБарса \nРеал \n\n19:00": "19:00",
    }
    for text, clock in samples.items():
        parsed = parse_ad_post(text, posted)
        assert parsed is not None
        assert parsed["slots"] == [f"2026-11-06T{clock}:00+03:00"]
        assert parsed["items"][0]["kind"] == "regular"


def test_plain_time_is_moscow_and_broadcast_word_can_sit_on_the_next_line():
    posted = datetime(2026, 11, 6, 18, 0, tzinfo=MSK)
    regular = parse_ad_post("22:00\n", posted)
    assert regular is not None
    assert regular["slots"] == ["2026-11-06T22:00:00+03:00"]
    assert regular["items"][0]["kind"] == "regular"
    broadcast = parse_ad_post("22:00\nтрансляция\n", posted)
    assert broadcast is not None
    assert broadcast["items"][0]["kind"] == "broadcast"
    mixed = parse_ad_post("11:00\n22:00 трансляция\n", posted)
    assert [item["kind"] for item in mixed["items"]] == ["regular", "broadcast"]


def test_news_text_is_not_an_ad_schedule():
    text = "Реклама в футболе мешает\nМанчестер Сити выиграл 2:1"
    posted = datetime(2026, 10, 22, 12, 0, tzinfo=MSK)
    assert parse_ad_post(text, posted) is None
