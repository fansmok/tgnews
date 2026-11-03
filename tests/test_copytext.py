import importlib.util
from pathlib import Path

from newsagent.copytext import BOLD_SPAN_RULE, clause_outside_title, detach_quote, keep_summary_fact, repeats_quote


def _write_copy():
    path = Path(__file__).resolve().parents[1] / "scripts" / "write_copy.py"
    spec = importlib.util.spec_from_file_location("write_copy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quote_leaves_the_title_and_stays_in_its_block():
    title, paragraphs, quote = detach_quote(
        "«Галатасарай» показал, как Батраков праздновал с фанатами: «Превратили стадион в Лилле в «Али Сами Йен»",
        ["На матче с «Лиллем» было 4:2, клуб отдельно отметил Алексея Батракова."],
        "Превратили стадион в Лилле в «Али Сами Йен»",
    )
    assert "Али Сами" not in title
    assert "4:2" in paragraphs[0]
    assert quote == "Превратили стадион в Лилле в «Али Сами Йен»"
    assert not repeats_quote(title, paragraphs, quote)


def test_paragraph_that_only_repeats_the_title_is_dropped():
    title, paragraphs, quote = detach_quote(
        "Батраков праздновал с фанатами",
        ["Батраков праздновал с фанатами"],
        "",
    )
    assert title == "Батраков праздновал с фанатами"
    assert paragraphs == []
    assert quote == ""


def test_paraphrase_of_the_title_is_dropped_and_the_quote_stays():
    title, paragraphs, quote = detach_quote(
        "Лионель Месси высказался об игре за «Барселону»",
        ["Лионель Месси поделился воспоминаниями о периоде выступлений за «Барселону»."],
        "Особенные чувства. Мы выиграли все и наслаждались победами, игрой и тренировками",
    )
    assert paragraphs == []
    assert quote.startswith("Особенные чувства")
    assert "Месси" in title


def test_paragraph_with_a_new_club_stays():
    title, paragraphs, quote = detach_quote(
        "«Хетафе» хочет подписать Серхио Рамоса зимой",
        ["Летом футболист покинул «Монтеррей»."],
        "",
    )
    assert paragraphs == ["Летом футболист покинул «Монтеррей»."]
    assert quote == ""


def test_summary_fact_stays_when_the_title_covers_the_story():
    title = "«ПСЖ» доволен Сафоновым и не будет искать нового вратаря зимой"
    summary = "«ПСЖ» не будет покупать нового вратаря в зимнее трансферное окно, несмотря на слухи."
    paragraphs = keep_summary_fact(title, [], summary)
    assert paragraphs == [summary]
    assert clause_outside_title(title, paragraphs[0]) == "несмотря на слухи"
    copy = _write_copy().normalize(
        {"title": title, "paragraphs": [], "bold_spans": [], "quote_text": "", "quote_author": ""},
        "source",
        summary=summary,
    )
    assert copy["paragraphs"] == [summary]
    assert copy["bold_spans"] == ["несмотря на слухи"]


def test_same_summary_does_not_become_a_second_title():
    title = "Батраков праздновал с фанатами"
    assert keep_summary_fact(title, [], title) == []


def test_prompt_asks_for_the_key_name_when_there_is_no_number():
    assert "ключевое имя" in BOLD_SPAN_RULE
    text = _write_copy().prompt(
        {"title": "Кэррик остаётся", "summary": "Рассматривают Нагельсманна", "url": ""},
        "Кэррик остаётся\nРассматривают Нагельсманна",
        "policy",
    )
    assert "ключевое имя человека" in text
    assert "Имя не выдумывай" in text


def test_telegram_source_asks_for_a_light_rewrite_instead_of_keeping_the_post():
    module = _write_copy()
    story = {"title": "КАРРИК ОСТАЁТСЯ!", "summary": "Рассматривают Нагельсманна", "url": "https://t.me/goaltime2026/1"}
    site = module.prompt(story, "Кэррик остаётся", "policy")
    telegram = module.prompt({**story, "source_kind": "telegram"}, "Кэррик остаётся", "policy")
    assert "лёгкий рерайт" in telegram and "без капса" in telegram
    assert "почти оставь" not in telegram
    assert "почти оставь" in site and "лёгкий рерайт" not in site
