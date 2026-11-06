from newsagent.lexicon import classify, load_lexicon


def test_world_football_stays_and_domestic_or_other_sports_drop():
    lexicon = load_lexicon()
    city = classify("Холанд оформил хет-трик за Манчестер Сити", "", lexicon)
    assert city["keep"] is True
    assert "man-city" in city["clubs"]

    galatasaray = classify("Батраков помог Галатасараю против Лилля", "", lexicon)
    assert galatasaray["keep"] is True
    assert "galatasaray" in galatasaray["clubs"]

    rpl = classify("Зенит обыграл Спартак в РПЛ", "", lexicon)
    assert rpl["keep"] is False
    assert rpl["drop_reason"] == "domestic_ru"

    nba = classify("Doncic outshines Curry with a half-court shot", "", lexicon)
    assert nba["keep"] is False

    united = classify("Man Utd humbled by four-goal Como", "", lexicon)
    assert united["keep"] is True
    assert "man-utd" in united["clubs"]


def test_formula_and_mail_digest_drop_even_with_a_foreign_club():
    lexicon = load_lexicon()
    formula = classify(
        "Schumacher visits Manchester United",
        "A paddock interview",
        lexicon,
        "https://www.theguardian.com/sport/auto/2026/oct/22/schumacher",
    )
    assert formula["keep"] is False
    assert formula["drop_reason"] == "other_sport"
    assert "man-utd" in formula["clubs"]

    named = classify(
        "Schumacher and Formula 1 after visiting Man Utd",
        "",
        lexicon,
        "https://example.com/motorsport",
    )
    assert named["drop_reason"] == "other_sport"

    digest = classify(
        "Football Daily: Man Utd lose at Como",
        "The best of the day's football",
        lexicon,
        "https://www.theguardian.com/football/2026/oct/22/football-daily",
    )
    assert digest["keep"] is False
    assert digest["drop_reason"] == "digest"

    match = classify("Como beat Man Utd 4:0", "", lexicon, "https://example.com/match")
    assert match["keep"] is True


def test_match_score_is_a_result_event():
    verdict = classify("Como beat Man Utd 4:0", "", load_lexicon())
    assert verdict["action"] == "result"
    assert "como" in verdict["clubs"]
    assert "man-utd" in verdict["clubs"]


def test_portsmouth_is_found_in_english_and_russian():
    lexicon = load_lexicon()
    en = classify("Mee call-up", "Portsmouth forward Kenny joins Northern Ireland", lexicon)
    assert "portsmouth" in en["clubs"]
    ru = classify("Вызов в сборную", "Нападающий «Портсмута» получил вызов", lexicon)
    assert "portsmouth" in ru["clubs"]


def test_merge_story_clubs_adds_second_club_from_copy():
    from newsagent.lexicon import merge_story_clubs

    merged = merge_story_clubs(
        ["man-utd"],
        "",
        "",
        "",
        "Вратарь «Манчестер Юнайтед» и нападающий «Портсмута» вызваны в сборную.",
    )
    assert merged == ["man-utd", "portsmouth"]


def test_merge_story_clubs_ignores_a_table_of_clubs():
    from newsagent.lexicon import merge_story_clubs

    merged = merge_story_clubs(
        ["arsenal"],
        "Суперкомпьютер не видит конкурентов «Арсеналу»",
        "1. Арсенал - 68,2%\n2. Борнмут - 0,4%\n3. Тоттенхэм - 0,1%\n4. Брентфорд - 0,2%",
    )
    assert merged == ["arsenal"]
