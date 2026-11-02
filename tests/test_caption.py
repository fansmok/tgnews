from newsagent.caption import longest_common_run, mostly_cyrillic, render_post, strip_ads, utf16_len


def test_caption_uses_bold_custom_emoji_and_instagram_quote():
    rendered = render_post(
        {
            "title": "Холанд оформил хет-трик",
            "paragraphs": ["Манчестер Сити обыграл Реал со счётом 4:2."],
            "bold_spans": ["4:2"],
            "title_emoji": {"custom_emoji_id": "5368324170671202286", "fallback": "⚽", "tags": ["man-city"]},
            "paragraph_emoji": [None],
            "quote": {"text": "Мы показали характер", "author": "Пеп Гвардиола"},
            "comment": "Город снова не оставил интриги.",
        }
    )
    assert "<b>Холанд оформил хет-трик</b>" in rendered["html"]
    assert "<b>4:2</b>" in rendered["html"]
    assert 'emoji-id="5368324170671202286"' in rendered["html"]
    assert "<blockquote>" in rendered["html"]
    assert "«Мы показали характер»" in rendered["html"]
    assert "— Пеп Гвардиола" in rendered["html"]
    assert rendered["html"].rstrip().endswith("</i>")
    bold = next(item for item in rendered["entities"] if item["type"] == "bold")
    assert bold["offset"] == utf16_len("⚽ ")
    assert rendered["visible_length"] <= 1000


def test_caption_renders_two_club_crests_on_the_title():
    rendered = render_post(
        {
            "title": "Фигу оценил трансферы между Барсой и Реалом",
            "paragraphs": ["Прямой переход сейчас маловероятен."],
            "bold_spans": [],
            "title_emoji": [
                {"custom_emoji_id": "111", "fallback": "🇪🇸", "tags": ["barcelona"]},
                {"custom_emoji_id": "222", "fallback": "🇪🇸", "tags": ["real-madrid"]},
            ],
            "paragraph_emoji": [None],
            "quote": None,
            "comment": None,
        }
    )
    assert 'emoji-id="111"' in rendered["html"]
    assert 'emoji-id="222"' in rendered["html"]
    assert '<tg-emoji emoji-id="111">🇪🇸</tg-emoji> <tg-emoji emoji-id="222">🇪🇸</tg-emoji> <b>' in rendered["html"]
    emojis = [item for item in rendered["entities"] if item["type"] == "custom_emoji"]
    assert len(emojis) == 2
    assert emojis[0]["custom_emoji_id"] == "111"
    assert emojis[1]["custom_emoji_id"] == "222"


def test_standard_emoji_is_plain_text():
    rendered = render_post(
        {
            "title": "Винисиус думает об Арсенале",
            "paragraphs": ["Реал рассматривает продажу."],
            "bold_spans": [],
            "title_emoji": {"fallback": "✍️", "tags": ["transfer"], "mode": "standard"},
            "paragraph_emoji": [{"fallback": "💰", "tags": ["transfer"], "mode": "standard"}],
            "quote": None,
            "comment": None,
        }
    )
    assert "tg-emoji" not in rendered["html"]
    assert rendered["html"].startswith("✍️ ")
    assert "💰" in rendered["html"]
    assert not any(item["type"] == "custom_emoji" for item in rendered["entities"])


def test_ad_lines_and_long_copies_are_caught():
    assert "промокод" not in strip_ads("Новость\nПромокод WINLINE внутри").lower()
    source = "Манчестер Сити объявил о трансфере защитника за восемьдесят миллионов"
    copied = "Манчестер Сити объявил о трансфере защитника за восемьдесят миллионов сегодня"
    assert longest_common_run(source, copied) >= 7
    rewritten = "Горожане закрыли переход центрального защитника. Сумма сделки — 80 млн евро."
    assert longest_common_run(source, rewritten) < 7


def test_comment_reactions_become_animated_emoji():
    rendered = render_post(
        {
            "title": "Кейн возглавил рейтинг",
            "paragraphs": [],
            "bold_spans": [],
            "title_emoji": {"custom_emoji_id": "1", "fallback": "🏆", "tags": ["trophy"]},
            "paragraph_emoji": [],
            "quote": None,
            "comment": "Заслужил?\n👍 — да\n🤔 — нет\n⚽️ лишнее",
        }
    )
    assert "tg-emoji" in rendered["html"]
    assert "👍" not in rendered["html"] or 'emoji-id="' in rendered["html"]
    assert rendered["html"].count("tg-emoji") >= 3
    assert "⚽️" not in rendered["plain"]
    assert any(item["type"] == "custom_emoji" and item["custom_emoji_id"] != "1" for item in rendered["entities"])


def test_russian_source_counts_as_cyrillic():
    assert mostly_cyrillic("Кэррик ответил Фернандешу после поражения Юнайтед")
    assert not mostly_cyrillic("Carrick hits back at Fernandes after the Como rout")
