from newsagent.custom_emoji import clubs_for_emoji


def test_copy_clubs_go_before_scout_noise_for_crest_order():
    story_clubs = ["man-city", "liverpool", "arsenal", "brighton"]
    copy = {
        "title": "«Арсенал» имеет все возможности, чтобы снова стать чемпионом Премьер-лиги",
        "paragraphs": [
            "Победа над «Ливерпулем» в воскресенье показала, что «канониры» получили более глубокий состав."
        ],
    }
    assert clubs_for_emoji(story_clubs, copy)[:2] == ["arsenal", "liverpool"]


def test_title_club_stays_ahead_of_body_club():
    ordered = clubs_for_emoji(
        ["chelsea", "arsenal"],
        {"title": "«Челси» обыграл соперника", "paragraphs": ["«Арсенал» проиграл второй матч подряд."]},
    )
    assert ordered[0] == "chelsea"
    assert "arsenal" in ordered
