import importlib.util
import json
from pathlib import Path

from newsagent.branding import pick_template
from newsagent.copytext import statement_missing_content
from newsagent.lexicon import detect_action
from newsagent.reactions import mismatched_reaction


def test_transfer_needs_a_whole_word():
    assert detect_action("«Не будут даже в переходных матчах». Аршавин — о «Локомотиве» и «Ахмате»") == "news"
    assert detect_action("The ideal design for a back four") == "news"
    assert detect_action("Кейн перейдёт в «Барселону»") == "transfer"
    assert detect_action("Liverpool sign Araujo") == "transfer"


def test_card_says_news_when_transfer_is_doubtful():
    opinion = {"action": "transfer", "title": "Аршавин о «Локомотиве» и «Ахмате»"}
    assert pick_template(opinion, {"title": "Аршавин о «Локомотиве» и «Ахмате»"}) == "main"
    interest = {"action": "transfer", "title": "«Реал» следит за Калафьори"}
    assert pick_template(interest, {"title": "«Реал» следит за Калафьори"}) == "transfer"


def test_statement_without_content_is_rejected():
    assert statement_missing_content(
        "В махачкалинском «Динамо» выступили с заявлением по поводу судейства в матче с «Ростовом»",
        ["Магомед Багаудинов опубликовал заявление по теме судейства арбитра Андрея Прокопова (0:3)."],
        None,
    )
    assert not statement_missing_content(
        "«Динамо» выступило с заявлением по судейству",
        ["Клуб потребовал отстранить арбитра Прокопова от матчей РПЛ."],
        None,
    )
    assert not statement_missing_content("«Вест Хэм» уволил Нуну", ["Португалец проработал год."], None)


def test_laugh_under_agreement_is_a_mismatch():
    assert mismatched_reaction("Поднимутся?\n🤣 — да, Шава все правильно говорит\n😭 — нет")
    assert not mismatched_reaction("❤️ — заберёт награду\n🤣 — слишком уверен в себе")
    assert not mismatched_reaction("💯 — да, прав\n👎 — нет")


def _voice_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "write_voice.py"
    spec = importlib.util.spec_from_file_location("write_voice_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_voice_skips_right_after_a_post_with_comment(tmp_path):
    voice = _voice_module()
    earlier = tmp_path / "R-20261104-0935-reg"
    later = tmp_path / "R-20261104-1110-reg"
    for path in (earlier, later):
        path.mkdir()
    (earlier / "machine.json").write_text(json.dumps({"status": "PASS"}))
    (earlier / "voice.json").write_text(json.dumps({"comment": "👍 — да\n👎 — нет"}))
    assert voice.previous_post(later)["comment"].startswith("👍")
    assert voice.previous_post(earlier) is None
    assert voice.used_symbols("👍 — да\n👎 — нет") == ["👍", "👎"]
