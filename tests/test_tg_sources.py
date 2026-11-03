from datetime import datetime, timedelta, timezone

from newsagent.tg_sources import (
    clean_post,
    collect_channels,
    fetch_channel,
    parse_preview,
    stale_reason,
)

NOW = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
EMOJI = '<tg-emoji emoji-id="1"><i class="emoji" style="background-image:url(\'//x/e.png\')"><b>{}</b></i></tg-emoji>'


def message(channel: str, post_id: int, body: str, *, hours_ago: float = 1, photo: bool = True, forwarded: bool = False) -> str:
    moment = (NOW - timedelta(hours=hours_ago)).isoformat()
    photo_html = (
        f'<a class="tgme_widget_message_photo_wrap" style="width:800px;background-image:url(\'https://cdn4.telesco.pe/file/{post_id}.jpg\')"></a>'
        if photo
        else ""
    )
    forwarded_html = '<div class="tgme_widget_message_forwarded_from">Forwarded</div>' if forwarded else ""
    return f"""
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message" data-post="{channel}/{post_id}">
        {forwarded_html}{photo_html}
        <div class="tgme_widget_message_text">{body}</div>
        <a class="tgme_widget_message_date"><time datetime="{moment}"></time></a>
      </div>
    </div>"""


def page(*messages: str) -> str:
    return "<html><body>" + "".join(messages) + "</body></html>"


TEN_HAG = (
    EMOJI.format("😡") + " <b>Эрик тен Хаг</b> о <b>Криштиану Роналду:</b><br/><br/>"
    "<blockquote><i>«Он уже не мог заставлять себя преодолевать боль. Если ты не в форме в Премьер-лиге — у тебя нет шансов».</i></blockquote><br/><br/>"
    + EMOJI.format("💬") + "<b> Ваш вердикт: Верное решение тренера или нет?</b><br/><br/>"
    + EMOJI.format("❤️") + "<b>— Да, все по факту сказал.</b><br/>"
    + EMOJI.format("👎") + "<b>— Нет, не согласен..</b><br/><br/>"
    + EMOJI.format("😍") + "<b> Переходи и ставь на матчи ЛЧ</b><br/><b>Ссылка: </b>"
    '<a href="https://lkeh.pro/x"><b>https://lkeh.pro/x</b></a>'
)


def test_preview_text_drops_source_emoji_and_keeps_inline_phrases():
    parsed = parse_preview(page(message("tutoffside", 5834, TEN_HAG)))
    assert parsed[0]["post"] == "tutoffside/5834"
    assert parsed[0]["image_urls"] == ["https://cdn4.telesco.pe/file/5834.jpg"]
    text = parsed[0]["text"]
    assert text.splitlines()[0] == "Эрик тен Хаг о Криштиану Роналду:"
    assert not any(char in text for char in "😡💬❤👎😍")


def test_poll_signature_and_betting_tail_are_cut_but_the_quote_stays():
    text = parse_preview(page(message("tutoffside", 5834, TEN_HAG)))[0]["text"]
    cleaned, reason = clean_post(text)
    assert reason == ""
    assert "«Он уже не мог" in cleaned
    for leftover in ("ставь", "Ссылка", "lkeh.pro", "Ваш вердикт", "— Да", "— Нет"):
        assert leftover not in cleaned


def test_betting_and_giveaway_posts_are_dropped_whole():
    for body in (
        "ЭКСПРЕСС НА 4 МАТЧА — КЭФФ 20.24\nАтлетико Мадрид - Бавария\nЗАБРАТЬ ЭТОТ ЭКСПРЕСС",
        "РАЗДАМ 500.000₽\nБез лишних слов - деньги разделю между 35-ю людьми, которые напишут мне в лс",
        "Вас упомянул администратор:\nСпециально для Вас, вход в VIP доступен ещё 30 минут",
    ):
        assert clean_post(body) == ("", "ad")


def test_channel_signature_lines_are_removed():
    text = "«Манчестер Юнайтед» может рассмотреть продажу Бруну Фернандеша следующим летом\nКонтракт истекает в июне\nGOALTIME\nНаши каналы | Мы в Max"
    cleaned, _ = clean_post(text, ["GOALTIME"])
    assert cleaned.splitlines() == [
        "«Манчестер Юнайтед» может рассмотреть продажу Бруну Фернандеша следующим летом",
        "Контракт истекает в июне",
    ]


def test_scores_results_and_tonight_previews_are_stale():
    assert stale_reason("«Барсу» массово тролят после 6:1 с «Алавесом»") == "score"
    assert stale_reason("«Ливерпуль» разгромил «Вест Хэм» на «Энфилде»") == "result"
    assert stale_reason("Если ПСЖ победит сегодня «Вильярреал», это станет 10-й победой подряд") == "today_match"
    assert stale_reason("Матч начнётся в 22:00, сбор команды в 19:30") == ""
    assert stale_reason("Арсенал — 68,2%, Сити — 18,9% по версии суперкомпьютера") == ""


def test_collect_keeps_fresh_news_and_skips_ads_scores_old_and_cross_channel_duplicates():
    death_a = "В возрасте 30 лет ушёл из жизни игрок «Тенерифе» Хесус де Мигель.<br/>Футболист столкнулся с вратарём во время матча, ночью Хесус скончался в больнице."
    death_b = "В ИСПАНИИ У ФУТБОЛИСТА ОСТАНОВИЛОСЬ СЕРДЦЕ!<br/>Вратарь «Андорры» ударил коленом в грудь нападающего Хесуса де Мигеля из «Тенерифе»."
    pages = {
        "nakorotke1": page(
            message("nakorotke1", 10, death_a, hours_ago=2),
            message("nakorotke1", 11, "«Барсу» массово тролят после 6:1 с «Алавесом»<br/>Соцсети завалили гифками с игроками «Барселоны»", hours_ago=3),
            message("nakorotke1", 12, "ЭКСПРЕСС НА 4 МАТЧА — КЭФФ 20.24<br/>Барселона - Астон Вилла", hours_ago=1),
        ),
        "tutoffside": page(
            message("tutoffside", 20, death_b, hours_ago=1),
            message("tutoffside", 21, "«Реал Мадрид» продлил контракт с Винисиусом до 2030 года<br/>Новое соглашение подписано в понедельник", hours_ago=30),
            message("tutoffside", 22, "Флик не рассчитывает на Гави в матче с «Реалом» из-за травмы колена<br/>Полузащитник «Барселоны» пропустит месяц", hours_ago=4, forwarded=True),
            message("tutoffside", 23, "Анчелотти сам решает, кого вызывать в сборную, — «Барселона» недовольна<br/>Рафинья получил три последние травмы в сборной", hours_ago=5, photo=False),
        ),
    }

    def loader(username, since):
        return fetch_channel(username, since, fetch=lambda name, before: pages[name] if before is None else page())

    channels = [{"username": "nakorotke1", "weight": 8}, {"username": "tutoffside", "weight": 8}]
    items, errors, skipped = collect_channels(channels, NOW, 24, loader=loader)
    assert errors == []
    assert len(items) == 1
    story = items[0]
    assert story["source_kind"] == "telegram"
    assert story["url"] in {"https://t.me/nakorotke1/10", "https://t.me/tutoffside/20"}
    assert story["image_urls"]
    assert skipped == {"score": 1, "ad": 1, "forwarded": 1, "no_image": 1}


def test_clubs_from_the_title_lead_the_list_for_title_badges():
    body = (
        "Суперкомпьютер не видит конкурентов «Арсеналу» в гонке за чемпионство АПЛ<br/>"
        "1. Арсенал - 68,2%<br/>2. Сити - 18,9%<br/>6. Борнмут - 0,4%<br/>9. Тоттенхэм - 0,1%"
    )
    items, _errors, _skipped = collect_channels(
        [{"username": "goaltime2026", "weight": 8}],
        NOW,
        24,
        loader=lambda username, since: parse_preview(page(message(username, 1, body))),
    )
    assert items[0]["clubs"] == ["arsenal"]


def test_fetch_channel_pages_back_until_the_window_is_covered():
    calls = []
    first = page(*[message("goaltime2026", post_id, "Новость", hours_ago=1) for post_id in (40, 41)])
    second = page(message("goaltime2026", 30, "Старая новость", hours_ago=40))

    def fetch(name, before):
        calls.append(before)
        return first if before is None else second

    rows = fetch_channel("goaltime2026", NOW - timedelta(hours=24), fetch=fetch)
    assert calls == [None, 40]
    assert [row["id"] for row in rows] == [30, 40, 41]
