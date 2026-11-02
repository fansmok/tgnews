from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from newsagent.feeds import dedupe_batch, parse_feed


def test_match_result_outranks_a_feature():
    published = format_datetime(datetime.now(timezone.utc) - timedelta(minutes=5))
    payload = f"""
    <rss version="2.0"><channel>
      <item>
        <title>Football Daily</title>
        <link>https://bbc.co.uk/sounds/play/p0phxkv1</link>
        <description>Reaction as Manchester United lose 4-1 at Como</description>
        <pubDate>{published}</pubDate>
      </item>
      <item>
        <title>From Bury to AC Milan: Bournemouth's journey to dreamland</title>
        <link>https://example.com/feature</link>
        <pubDate>{published}</pubDate>
      </item>
      <item>
        <title>Como beat Man Utd 4-0</title>
        <link>https://example.com/match</link>
        <pubDate>{published}</pubDate>
      </item>
    </channel></rss>
    """.encode()
    source = {"id": "bbc", "weight": 10, "lang": "en"}
    items = dedupe_batch(parse_feed(payload, source, datetime.now(timezone.utc), 12))
    assert items[0]["url"].endswith("/match")
    assert items[0]["action"] == "result"
    assert all("/sounds/" not in item["url"] for item in items)


def test_formula_section_and_football_daily_never_enter_the_batch():
    published = format_datetime(datetime.now(timezone.utc) - timedelta(minutes=5))
    payload = f"""
    <rss version="2.0"><channel>
      <item>
        <title>Schumacher visits Manchester United</title>
        <link>https://www.theguardian.com/sport/auto/2026/oct/22/schumacher</link>
        <description>Formula 1 driver in the paddock</description>
        <pubDate>{published}</pubDate>
      </item>
      <item>
        <title>Football Daily: Man Utd lose at Como</title>
        <link>https://www.theguardian.com/football/2026/oct/22/football-daily</link>
        <description>The best of the day's football</description>
        <pubDate>{published}</pubDate>
      </item>
      <item>
        <title>Como beat Man Utd 4-0</title>
        <link>https://example.com/match</link>
        <pubDate>{published}</pubDate>
      </item>
    </channel></rss>
    """.encode()
    source = {"id": "guardian", "weight": 8, "lang": "en"}
    urls = [item["url"] for item in parse_feed(payload, source, datetime.now(timezone.utc), 12)]
    assert urls == ["https://example.com/match"]


def test_stale_result_and_lineup_are_skipped_for_todays_story():
    now = datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc)
    stale = format_datetime(now - timedelta(minutes=40))
    earlier = format_datetime(now - timedelta(hours=4))
    payload = f"""
    <rss version="2.0"><channel>
      <item>
        <title>Como beat Man Utd 4-0</title>
        <link>https://example.com/stale-result</link>
        <pubDate>{stale}</pubDate>
      </item>
      <item>
        <title>Arsenal starting XI to face Chelsea</title>
        <link>https://example.com/stale-xi</link>
        <description>lineup</description>
        <pubDate>{stale}</pubDate>
      </item>
      <item>
        <title>Man Utd agree a deal for a midfielder</title>
        <link>https://example.com/deal</link>
        <pubDate>{earlier}</pubDate>
      </item>
    </channel></rss>
    """.encode()
    source = {"id": "bbc", "weight": 10, "lang": "en"}
    items = parse_feed(payload, source, now, 12)
    urls = [item["url"] for item in items]
    assert "https://example.com/stale-result" not in urls
    assert "https://example.com/stale-xi" not in urls
    assert "https://example.com/deal" in urls


def test_video_sportsru_and_video_digests_are_skipped():
    now = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)
    published = format_datetime(now - timedelta(minutes=15))
    payload = f"""
    <rss version="2.0"><channel>
      <item>
        <title>Видео: обзор матча Реал Мадрид</title>
        <link>https://video.sports.ru/football/123.html</link>
        <pubDate>{published}</pubDate>
      </item>
      <item>
        <title>Видеодайджест лучших голов тура</title>
        <link>https://www.sports.ru/football/456.html</link>
        <description>Видеодайджест европейских чемпионатов</description>
        <pubDate>{published}</pubDate>
      </item>
      <item>
        <title>Реал Мадрид согласовал контракт с защитником</title>
        <link>https://www.sports.ru/football/789.html</link>
        <pubDate>{published}</pubDate>
      </item>
    </channel></rss>
    """.encode()
    source = {"id": "sportsru", "weight": 9, "lang": "ru"}
    items = parse_feed(payload, source, now, 12)
    urls = [item["url"] for item in items]
    assert "https://video.sports.ru/football/123.html" not in urls
    assert not any("456" in u for u in urls)
    assert "https://sports.ru/football/789.html" in urls

