from newsagent.custom_emoji import pick_custom


CATALOG = {
    "items": [
        {"custom_emoji_id": "1", "fallback": "💸", "set_name": "NewsEmoji", "tags": ["transfer"]},
        {"custom_emoji_id": "2", "fallback": "💸", "set_name": "NewsEmoji", "tags": ["transfer"]},
        {"custom_emoji_id": "3", "fallback": "⚽️", "set_name": "foot_flags_by_fStikBot", "tags": ["football"]},
        {"custom_emoji_id": "4", "fallback": "🇮🇹", "set_name": "FC_logos", "tags": ["club-logo"]},
        {"custom_emoji_id": "5", "fallback": "🏆", "set_name": "futbol_icon", "tags": ["trophy"]},
        {"custom_emoji_id": "6", "fallback": "💵", "set_name": "RestrictedEmoji", "tags": ["transfer"]},
    ]
}


def test_transfer_uses_news_pack_not_a_club_crest_or_old_pack():
    picked = pick_custom({"url": "https://example.com/a", "action": "transfer", "clubs": ["real-madrid"]}, {}, "transfer", CATALOG)
    assert picked["title_emoji"]["set_name"] == "NewsEmoji"
    assert picked["title_emoji"]["fallback"] == "💸"
    assert picked["title_emoji"]["custom_emoji_id"] in {"1", "2"}


def test_same_story_keeps_the_same_emoji():
    story = {"url": "https://example.com/a", "action": "transfer"}
    first = pick_custom(story, {}, "transfer", CATALOG)
    second = pick_custom(story, {}, "transfer", CATALOG)
    assert first["title_emoji"]["custom_emoji_id"] == second["title_emoji"]["custom_emoji_id"]


def test_plain_news_emoji_is_tagged_for_the_story_gate():
    picked = pick_custom({"url": "https://example.com/news", "action": "news", "clubs": ["bayern"]}, {}, "main", CATALOG)
    assert picked["title_emoji"]["tags"] == ["news"]
    assert picked["title_emoji"]["fallback"] == "⚽️"


def test_both_club_crests_go_on_the_title_when_story_has_two_clubs():
    catalog = {
        "items": CATALOG["items"]
        + [
            {"custom_emoji_id": "90", "fallback": "🇩🇪", "set_name": "FC_logos", "tags": ["bayern"]},
            {"custom_emoji_id": "91", "fallback": "🇩🇪", "set_name": "FC_logos", "tags": ["dortmund"]},
        ]
    }
    picked = pick_custom(
        {"url": "https://example.com/derby", "action": "result", "clubs": ["bayern", "dortmund"]},
        {"paragraphs": ["Бавария принимает Боруссию."]},
        "result",
        catalog,
    )
    assert isinstance(picked["title_emoji"], list)
    assert len(picked["title_emoji"]) == 2
    assert picked["title_emoji"][0]["custom_emoji_id"] == "90"
    assert picked["title_emoji"][0]["tags"] == ["bayern"]
    assert picked["title_emoji"][1]["custom_emoji_id"] == "91"
    assert picked["title_emoji"][1]["tags"] == ["dortmund"]


def test_fc_logo_title_uses_ball_fallback_not_country_flag():
    catalog = {
        "items": CATALOG["items"]
        + [
            {"custom_emoji_id": "90", "fallback": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "set_name": "FC_logos", "tags": ["man-city"]},
            {"custom_emoji_id": "91", "fallback": "🇪🇸", "set_name": "FC_logos", "tags": ["real-madrid"]},
        ]
    }
    picked = pick_custom(
        {"url": "https://example.com/ucl", "action": "news", "clubs": ["man-city", "real-madrid"]},
        {"paragraphs": ["Матч в ЛЧ."]},
        "main",
        catalog,
    )
    assert picked["title_emoji"][0]["fallback"] == "⚽"
    assert picked["title_emoji"][1]["fallback"] == "⚽"


def test_result_uses_the_ball_from_the_football_pack():
    picked = pick_custom({"url": "https://example.com/match", "action": "result"}, {}, "result", CATALOG)
    assert picked["title_emoji"]["set_name"] == "foot_flags_by_fStikBot"
    assert picked["title_emoji"]["fallback"] == "⚽️"
