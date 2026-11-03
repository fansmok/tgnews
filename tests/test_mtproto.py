import asyncio

from newsagent import mtproto


def test_is_cursor_cloud_detects_agent_env(monkeypatch):
    monkeypatch.delenv("CURSOR_AGENT", raising=False)
    monkeypatch.delenv("CLOUD_AGENT_INJECTED_SECRET_NAMES", raising=False)
    assert mtproto.is_cursor_cloud() is False
    monkeypatch.setenv("CURSOR_AGENT", "1")
    monkeypatch.setenv("CLOUD_AGENT_INJECTED_SECRET_NAMES", "TELEGRAM_BOT_TOKEN")
    assert mtproto.is_cursor_cloud() is True


def test_format_mtproto_error_cloud_hint(monkeypatch):
    monkeypatch.setenv("CURSOR_AGENT", "1")
    monkeypatch.setenv("CLOUD_AGENT_INJECTED_SECRET_NAMES", "x")
    err = asyncio.IncompleteReadError(b"x" * 146, 1347703872)
    text = mtproto.format_mtproto_error(err)
    assert "Cursor Cloud Agent" in text
    assert "private worker" in text


def test_publish_needs_mtproto_only_when_allow_and_session(monkeypatch):
    monkeypatch.setenv("PUBLISH_ALLOW", "no")
    monkeypatch.setenv("TELEGRAM_STRING_SESSION", "s")
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    assert mtproto.publish_needs_mtproto() is False
    monkeypatch.setenv("PUBLISH_ALLOW", "yes")
    assert mtproto.publish_needs_mtproto() is True
