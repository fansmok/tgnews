from PIL import Image

from newsagent.branding import boxes_overlap, choose_size, compose, draw_logo, pick_template, pillow_footer


def test_pillow_fallback_signs_the_brand_not_the_source():
    assert pillow_footer({"source_id": "championat"}) == "GOL88.RU"


def test_fresh_result_uses_result_template():
    assert pick_template({"action": "result"}, {}) == "result"
    assert pick_template({"action": "lineup"}, {}) == "fixture"
    assert pick_template({"action": "news"}, {"quote": {"text": "Мы готовы"}}) == "quote"
    assert pick_template({"action": "transfer", "title": "Сафонов перейдёт в ПСЖ"}, {}) == "transfer"


def test_refusal_to_buy_without_a_fee_is_a_news_card():
    story = {
        "action": "transfer",
        "title": "«ПСЖ» доволен Сафоновым и не будет искать нового вратаря зимой",
        "summary": "«ПСЖ» не будет покупать нового вратаря в зимнее трансферное окно, несмотря на слухи.",
    }
    assert pick_template(story, {"title": story["title"], "paragraphs": [story["summary"]]}) == "main"


def test_priced_or_agreed_transfer_stays_on_the_transfer_card():
    priced = {"action": "transfer", "title": "«ПСЖ» купит вратаря за 40 млн евро"}
    agreed = {"action": "transfer", "title": "Не будет искать других: Сафонов подписал контракт"}
    assert pick_template(priced, {}) == "transfer"
    assert pick_template(agreed, {}) == "transfer"


def test_photo_is_not_upscaled_and_badge_stays_inside():
    source = Image.new("RGB", (2000, 1200), (20, 40, 80))
    image, meta = compose(source, template="main", headline="Батраков праздновал с фанатами", footer="sportsru")
    assert image.size == (600, 600)
    assert image.size == (meta["width"], meta["height"])
    badge = tuple(meta["slots"]["badge"])
    assert badge[0] >= 0 and badge[1] >= 0
    assert badge[0] + badge[2] <= image.width
    assert not boxes_overlap(tuple(meta["slots"]["badge"]), tuple(meta["slots"]["logo"]))
    assert not boxes_overlap(tuple(meta["slots"]["headline"]), tuple(meta["slots"]["logo"]))
    assert not boxes_overlap(tuple(meta["slots"]["headline"]), tuple(meta["slots"]["footer"]))
    logo = draw_logo(128)
    assert logo.mode == "RGBA"
    assert logo.getpixel((64, 64))[3] == 255


def test_every_template_keeps_layers_apart():
    source = Image.new("RGB", (1800, 1000), (30, 50, 90))
    facts = {
        "summary": "Коротко о событии дня",
        "quote": "Мы не думаем о прошлом",
        "attribution": "Главный тренер",
        "home": "МАН СИТИ",
        "away": "АРСЕНАЛ",
        "score": "2 : 1",
        "competition": "АПЛ · 36 ТУР",
        "kickoff": "16:00",
        "venue": "Этихад",
        "when": "12.04 20:00",
        "amount": "45 млн евро",
        "stat_value": "32",
        "stat_label": "голы в сезоне",
    }
    names = ["main", "urgent", "transfer", "insider", "quote", "result", "fixture", "stats", "scandal", "meme"]
    for name in names:
        image, meta = compose(source, template=name, headline="Заголовок новости в несколько строк", footer="sports.ru", facts=facts)
        assert meta["template"] == name
        assert image.size == (600, 600)
        slots = meta["slots"]
        assert not boxes_overlap(tuple(slots["badge"]), tuple(slots["logo"]))
        assert not boxes_overlap(tuple(slots["headline"]), tuple(slots["logo"]))
        assert not boxes_overlap(tuple(slots["headline"]), tuple(slots["footer"]))
        assert not boxes_overlap(tuple(slots["badge"]), tuple(slots["headline"]))
        assert image.size == (meta["width"], meta["height"])


def test_every_post_is_600_square():
    source = Image.new("RGB", (700, 400), (10, 10, 10))
    chosen = choose_size(source.width, source.height, "landscape")
    assert (chosen["width"], chosen["height"]) == (600, 600)
    image, meta = compose(source, template="main", headline="Короткий заголовок", footer="sports.ru")
    assert image.size == (600, 600)
    assert meta["width"] == 600
