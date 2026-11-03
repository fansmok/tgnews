from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from newsagent.memory import (
    connect,
    is_duplicate,
    prune_history,
    release_story_reservation,
    remember_story,
    reserve_story,
    try_lock_slot,
)

MSK = ZoneInfo("Europe/Moscow")


def test_story_url_reservation_is_atomic_and_releasable(tmp_path):
    item = {"url": "https://example.com/story?utm_source=rss", "title": "Story"}
    first = connect(tmp_path / "news.db")
    second = connect(tmp_path / "news.db")
    assert reserve_story(first, item) is True
    assert reserve_story(second, dict(item, url="https://example.com/story")) is False
    release_story_reservation(first, item)
    assert reserve_story(second, item) is True


def test_same_url_and_same_match_are_duplicates(tmp_path):
    conn = connect(tmp_path / "news.db")
    item = {
        "url": "https://www.bbc.com/sport/football/story?utm_source=rss",
        "title": "Como thrash Man Utd 4-0",
        "event_key": "2026-10-22|result|como,man-utd",
        "action": "result",
        "clubs": ["como", "man-utd"],
        "source_id": "bbc",
        "published_at": "2026-10-22T12:00:00+03:00",
    }
    remember_story(conn, item, "sent")
    same_url = dict(item, url="https://bbc.com/sport/football/story")
    assert is_duplicate(conn, same_url)[0] is True

    other_words = dict(
        item,
        url="https://marca.com/other",
        title="Manchester United collapse against Como",
    )
    assert is_duplicate(conn, other_words) == (True, "match")

    fresh = {
        "url": "https://bbc.com/sport/football/other",
        "title": "Saka injury worries Arsenal before Bayern",
        "event_key": "2026-10-22|injury|arsenal,bayern",
        "action": "injury",
        "clubs": ["arsenal", "bayern"],
    }
    assert is_duplicate(conn, fresh)[0] is False


def test_same_player_and_club_on_the_same_day_is_duplicate_across_angles(tmp_path):
    conn = connect(tmp_path / "news.db")
    remember_story(
        conn,
        {
            "url": "https://sports.ru/football/batrakov-fans",
            "title": "«Галатасарай» показал, как Батраков праздновал с фанатами",
            "event_key": "2026-10-22|result|galatasaray",
            "action": "result",
            "clubs": ["galatasaray"],
        },
        "sent",
    )
    other_angle = {
        "url": "https://championat.com/football/batrakov-board",
        "title": "В руководстве «Галатасарая» оценили влияние Батракова на результаты клуба",
        "event_key": "2026-10-22|transfer|galatasaray",
        "action": "transfer",
        "clubs": ["galatasaray"],
    }
    assert is_duplicate(conn, other_angle) == (True, "player")

    other_player = {
        "url": "https://championat.com/football/galatasaray-coach",
        "title": "Галатасарай объявил, что Виктор Осимхен останется в клубе",
        "event_key": "2026-10-22|news|galatasaray",
        "action": "news",
        "clubs": ["galatasaray"],
    }
    assert is_duplicate(conn, other_player)[0] is False


def test_english_retelling_matches_same_player_not_other_club_news(tmp_path):
    conn = connect(tmp_path / "news.db")
    remember_story(
        conn,
        {
            "url": "https://sports.ru/football/carrick-stays",
            "title": "«МЮ» не уволит Кэррика до матча с «Борнмутом». В качестве замены рассматривают Нагельсманна",
            "event_key": "2026-10-22|sack|man-utd",
            "action": "sack",
            "clubs": ["man-utd"],
        },
        "sent",
    )
    english = {
        "url": "https://bbc.co.uk/sport/football/articles/carrick",
        "title": "Carrick carrying on as normal as Man Utd eye possible replacements",
        "event_key": "2026-10-22|news|bournemouth,man-utd",
        "action": "news",
        "clubs": ["man-utd", "bournemouth"],
    }
    assert is_duplicate(conn, english) == (True, "player")

    next_day_english = {
        "url": "https://espn.com/soccer/story/carrick-next-day",
        "title": "Sources: Under-fire Carrick to lead Man United on Sunday",
        "event_key": "2026-10-23|news|bournemouth,man-utd",
        "action": "news",
        "clubs": ["bournemouth", "man-utd"],
    }
    assert is_duplicate(conn, next_day_english) == (True, "player")

    other_plot = {
        "url": "https://espn.com/soccer/story/clearout",
        "title": "Transfer rumors, news: Man United consider defensive clearout in summer",
        "event_key": "2026-10-22|transfer|man-utd",
        "action": "transfer",
        "clubs": ["man-utd"],
    }
    assert is_duplicate(conn, other_plot)[0] is False


def test_short_surname_same_player_and_club_is_not_a_second_url(tmp_path):
    conn = connect(tmp_path / "news.db")
    remember_story(
        conn,
        {
            "url": "https://sports.ru/football/dias-thigh",
            "title": "У Диаса повреждение задней поверхности левого бедра. Вингер «Баварии» травмировался в матче с «Арсеналом» после выхода на замену",
            "event_key": "2026-10-22|injury|arsenal,bayern",
            "action": "injury",
            "clubs": ["arsenal", "bayern"],
        },
        "sent",
    )
    championat = {
        "url": "https://championat.com/football/news-6668126-poluzaschitnik-bavarii-luis-dias.html",
        "title": "Полузащитник «Баварии» Луис Диас выбыл из строя на срок до шести недель из-за травмы",
        "event_key": "2026-10-22|injury|arsenal,bayern",
        "action": "injury",
        "clubs": ["arsenal", "bayern"],
    }
    assert is_duplicate(conn, championat) == (True, "player")

    english = dict(
        championat,
        url="https://bbc.com/sport/football/dias-out",
        title="Bayern winger Luis Dias sidelined after the Arsenal match",
    )
    assert is_duplicate(conn, english) == (True, "player")

    other_player = {
        "url": "https://championat.com/football/kane-bayern",
        "title": "Харри Кейн забил за «Баварию» в матче с «Арсеналом»",
        "event_key": "2026-10-22|result|arsenal,bayern",
        "action": "result",
        "clubs": ["arsenal", "bayern"],
    }
    assert is_duplicate(conn, other_player)[0] is False

    club_word = {
        "url": "https://sports.ru/football/como-contract",
        "title": "«Комо» продлил контракт с Осимхеном до конца года",
        "event_key": "2026-10-22|transfer|como",
        "action": "transfer",
        "clubs": ["como"],
    }
    remember_story(
        conn,
        {
            "url": "https://sports.ru/football/como-injury",
            "title": "«Комо» сообщил о травме Каннаваро в этом году",
            "event_key": "2026-10-22|injury|como",
            "action": "injury",
            "clubs": ["como"],
        },
        "sent",
    )
    assert is_duplicate(conn, club_word)[0] is False


def test_surname_hidden_in_the_slug_still_matches_the_same_player(tmp_path):
    conn = connect(tmp_path / "news.db")
    remember_story(
        conn,
        {
            "url": "https://sports.ru/football/carrick-stays",
            "title": "«МЮ» не уволит Кэррика до матча с «Борнмутом». В качестве замены рассматривают Нагельсманна",
            "event_key": "2026-10-22|sack|man-utd",
            "action": "sack",
            "clubs": ["man-utd"],
        },
        "sent",
    )
    remember_story(
        conn,
        {
            "url": "https://bbc.com/sport/football/carrick-como",
            "title": "Carrick hits back after Como rout",
            "event_key": "2026-10-22|result|como,man-utd",
            "action": "result",
            "clubs": ["como", "man-utd"],
        },
        "sent",
    )
    successor = {
        "url": "https://theguardian.com/football/2026/oct/22/contenders-manchester-united-next-manager-michael-carrick",
        "title": "Next in line? Main contenders for the Manchester United hot seat",
        "event_key": "2026-10-22|sack|como,man-utd",
        "action": "sack",
        "clubs": ["man-utd", "como"],
    }
    assert is_duplicate(conn, successor) == (True, "player")

    shortlist = {
        "url": "https://theguardian.com/football/2026/oct/22/manchester-united-next-manager-shortlist",
        "title": "Manchester United weigh a shortlist for the dugout",
        "event_key": "2026-10-22|sack|man-utd",
        "action": "sack",
        "clubs": ["man-utd"],
    }
    assert is_duplicate(conn, shortlist)[0] is False


def test_slot_lock_is_exclusive_until_released(tmp_path):
    first = connect(tmp_path / "news.db")
    second = connect(tmp_path / "news.db")
    moment = datetime(2026, 10, 22, 12, 0, tzinfo=MSK)
    assert try_lock_slot(first, moment, "run-a") is True
    assert try_lock_slot(second, moment, "run-b") is False
    first.execute("UPDATE slots SET status = 'skipped'")
    first.commit()
    assert try_lock_slot(second, moment, "run-b") is True


def test_stories_older_than_two_days_are_forgotten(tmp_path):
    conn = connect(tmp_path / "news.db")
    old = (datetime.now(MSK) - timedelta(days=3)).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO stories (url, title, title_norm, event_key, action, source_id, published_at, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "https://bbc.com/old-story",
            "Old story about a match",
            "old story about a match",
            "2026-10-19|news|arsenal",
            "news",
            "bbc",
            old,
            old,
            "sent",
        ),
    )
    conn.commit()
    same = {
        "url": "https://bbc.com/old-story",
        "title": "Old story about a match",
        "event_key": "2026-10-19|news|arsenal",
        "action": "news",
        "clubs": ["arsenal"],
    }
    assert is_duplicate(conn, same)[0] is False
    left = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
    assert left == 0


def test_picked_story_blocks_other_batch_slot_but_not_its_own_publish(tmp_path):
    from newsagent.memory import pick_story_record

    conn = connect(tmp_path / "news.db")
    today = datetime.now(MSK).date().isoformat()
    picked = {
        "url": "https://sports.ru/football/calafiori-real",
        "title": "«Реал» следит за Калафьори",
        "event_key": f"{today}|transfer|arsenal,real-madrid",
        "action": "transfer",
    }
    assert pick_story_record(conn, picked) is True
    other_source = dict(picked, url="https://championat.com/calafiori", title="«Реал Мадрид» интересуется Калафьори")
    assert is_duplicate(conn, other_source)[0] is True
    assert is_duplicate(conn, picked)[0] is True
    assert is_duplicate(conn, picked, own=True)[0] is False
    assert reserve_story(conn, picked) is True
    release_story_reservation(conn, picked)
    assert reserve_story(conn, picked) is True


def test_post_duplicate_matches_channel_titles():
    from newsagent.memory import post_duplicate

    assert post_duplicate(
        "🇪🇸 «Реал Мадрид» интересуется левым защитником «Арсенала» Калафьори",
        "🇪🇸 «Реал» следит за левым защитником «Арсенала» Калафьори",
    )
    assert post_duplicate(
        "🇹🇷 🇮🇹 Габриэл Сара из «Галатасарая» интересен «Роме»",
        "🇹🇷 🇮🇹 «Рома» заинтересовалась центральным полузащитником «Галатасарая» Габриэлом Сарой",
    )
    assert post_duplicate(
        "Гарри Кейн сообщил, что новый контракт с «Баварией» чрезвычайно близок",
        "Новый контракт Кейна с «Баварией» крайне близок и будет оформлен в ближайшие дни",
    )
    assert not post_duplicate(
        "🚨 «Вест Хэм» уволил главного тренера Нуну Эшпириту Санту",
        "🏴 Как Артета выжимает максимум из Деклана Райса",
    )
    assert not post_duplicate(
        "Олисе тренировался перед матчем с «Атлетико»",
        "«Ливерпуль» хочет оформить трансфер Араухо в январе",
    )
