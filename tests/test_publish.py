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


def test_publish_error_never_exposes_bot_token(monkeypatch):
    publish = _publish_module()
    token = "123456:abcdefghijklmnopqrstuvwxyz"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    request = httpx.Request("POST", f"https://api.telegram.org/bot{token}/sendPhoto")
    error = httpx.RequestError(f"request to {request.url} failed", request=request)
    detail = publish.safe_error(error)
    assert token not in detail
    assert detail == "Telegram request failed: RequestError"
