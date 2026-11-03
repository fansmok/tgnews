import importlib.util
import sys
from pathlib import Path

import httpx

from newsagent.runtime import write_json


def _publish_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "publish.py"
    spec = importlib.util.spec_from_file_location("publish_script", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_publish_is_idempotent_after_message_id_exists(tmp_path, monkeypatch, capsys):
    publish = _publish_module()
    write_json(tmp_path / "publish-result.json", {"status": "sent", "message_id": "123"})
    monkeypatch.setattr(sys, "argv", ["publish.py", "--run-dir", str(tmp_path)])
    assert publish.main() == 0
    assert "already_published message_id=123" in capsys.readouterr().out


def test_schedule_matches_future_slot():
    publish = _publish_module()
    from datetime import datetime
    from zoneinfo import ZoneInfo

    msk = ZoneInfo("Europe/Moscow")
    target = datetime(2026, 11, 3, 18, 0, tzinfo=msk)
    assert publish.schedule_matches(int(target.timestamp()), target)
    assert not publish.schedule_matches(int(target.timestamp()) - 3600, target)


def test_has_custom_emoji_detects_entities():
    publish = _publish_module()
    assert publish.has_custom_emoji({"entities": [{"type": "custom_emoji", "custom_emoji_id": "1"}]})
    assert not publish.has_custom_emoji({"entities": [{"type": "bold"}]})


def test_publish_error_never_exposes_bot_token(monkeypatch):
    publish = _publish_module()
    token = "123456:abcdefghijklmnopqrstuvwxyz"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    request = httpx.Request("POST", f"https://api.telegram.org/bot{token}/sendPhoto")
    error = httpx.RequestError(f"request to {request.url} failed", request=request)
    detail = publish.safe_error(error)
    assert token not in detail
    assert detail == "Telegram request failed: RequestError"

