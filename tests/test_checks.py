from PIL import Image

from newsagent.checks import machine_check
from newsagent.runtime import write_json


def _ready_run(tmp_path):
    Image.new("RGB", (800, 600), "green").save(tmp_path / "photo.jpg")
    Image.new("RGB", (600, 600), "green").save(tmp_path / "designed.jpg")
    write_json(
        tmp_path / "story.json",
        {
            "url": "https://example.com/news",
            "title": "Новая футбольная новость",
            "summary": "",
            "clubs": [],
            "competitions": [],
            "action": "news",
        },
    )
    write_json(
        tmp_path / "copy.json",
        {
            "title": "Новая футбольная новость",
            "paragraphs": [],
            "bold_spans": [],
            "quote": None,
            "source_text": "",
        },
    )
    write_json(
        tmp_path / "emoji.json",
        {
            "title_emoji": {
                "custom_emoji_id": "5382357040008021292",
                "fallback": "🆕",
                "tags": ["news"],
                "set_name": "NewsEmoji",
            },
            "paragraph_emoji": [],
        },
    )
    write_json(tmp_path / "voice.json", {"comment": None, "reason": "not_needed"})
    write_json(
        tmp_path / "photo.json",
        {"status": "ok", "file": "photo.jpg", "width": 800, "height": 600},
    )
    write_json(
        tmp_path / "design.json",
        {"status": "ok", "file": "designed.jpg", "width": 600, "height": 600},
    )
    write_json(tmp_path / "photo-review.json", {"verdict": "PASS"})
    write_json(tmp_path / "slot-plan.json", {"publish_at": "2026-10-22T22:00:00+03:00", "reason": "regular"})
    write_json(tmp_path / "memory-decision.json", {"duplicate": False})


def test_machine_requires_designed_image_and_photo_review(tmp_path):
    _ready_run(tmp_path)
    assert machine_check(tmp_path)["status"] == "PASS"

    (tmp_path / "designed.jpg").unlink()
    report = machine_check(tmp_path)
    assert report["status"] == "FAIL"
    assert report["checks"]["design"]["status"] == "FAIL"


def test_machine_rejects_photo_review_rework(tmp_path):
    _ready_run(tmp_path)
    write_json(tmp_path / "photo-review.json", {"verdict": "REWORK", "target": "fn-design"})
    report = machine_check(tmp_path)
    assert report["status"] == "FAIL"
    assert report["checks"]["photo_review"]["status"] == "FAIL"


def test_machine_checks_telegram_utf16_limit(tmp_path):
    _ready_run(tmp_path)
    copy = {
        "title": "Новая футбольная новость",
        "paragraphs": ["😀" * 600],
        "bold_spans": ["😀"],
        "quote": None,
        "source_text": "",
    }
    write_json(tmp_path / "copy.json", copy)
    report = machine_check(tmp_path)
    assert report["status"] == "FAIL"
    assert report["checks"]["length"]["status"] == "FAIL"
