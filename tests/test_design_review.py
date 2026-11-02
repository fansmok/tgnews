import sys
from argparse import Namespace
from pathlib import Path

from newsagent.design_review import extreme_design_issues
from newsagent.runtime import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pipeline  # noqa: E402


def test_cosmetic_kie_notes_do_not_rebuild():
    issues = [
        "На карточке внизу чужой бренд GOL88.RU — убрать водяной знак",
        "На ноге видны артефакты генерации, деформация голени",
        "Можно чуть лучше кадрировать",
    ]
    assert extreme_design_issues(issues) == []


def test_extreme_card_failure_still_rebuilds():
    issues = ["Кадр не футбол, на фото баскетбол", "Чужой логотип СМИ закрывает лицо"]
    assert extreme_design_issues(issues) == issues


def test_rework_keeps_the_card_when_the_critic_is_picky(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    write_json(
        run / "critic.json",
        {
            "verdict": "REWORK",
            "target": "fn-design",
            "issues": ["Плашка GOL88.RU выглядит как реклама", "Слегка кривая кисть"],
        },
    )
    code = pipeline.stage_rework(Namespace(run_dir=str(run), target="fn-design"))
    assert code == 0
    saved = read_json(run / "critic.json")
    assert saved["verdict"] == "PASS"
    assert saved["issues"] == []
