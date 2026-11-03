"""Telethon (MTProto) helpers: probe, retries, cloud detection."""
from __future__ import annotations

import os
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def is_cursor_cloud() -> bool:
    return os.environ.get("CURSOR_AGENT", "").strip() == "1" and bool(
        os.environ.get("CLOUD_AGENT_INJECTED_SECRET_NAMES", "").strip()
    )


def user_session_ready() -> bool:
    return bool(
        os.environ.get("TELEGRAM_STRING_SESSION")
        and os.environ.get("TELEGRAM_API_ID")
        and os.environ.get("TELEGRAM_API_HASH")
    )


def publish_needs_mtproto() -> bool:
    if os.environ.get("PUBLISH_ALLOW", "no").strip().lower() != "yes":
        return False
    return user_session_ready()


def format_mtproto_error(exc: BaseException) -> str:
    name = exc.__class__.__name__
    text = str(exc)
    if "IncompleteReadError" in name or "146 bytes read" in text or "1347703872" in text:
        hint = (
            "MTProto недоступен в этой среде (часто Cursor Cloud Agent). "
            "Публикуйте с Mac/VPS или запустите automation на private worker с доступом к Telegram."
        )
        if is_cursor_cloud():
            return hint
        return f"Telethon connect failed: {name}"
    if len(text) > 400:
        text = text[:400]
    return f"Telethon: {text or name}"


def _client_factory():
    from telethon.sessions import StringSession
    from telethon.sync import TelegramClient

    return TelegramClient(
        StringSession(os.environ["TELEGRAM_STRING_SESSION"]),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"],
        timeout=15,
        connection_retries=1,
        retry_delay=1,
        auto_reconnect=False,
    )


def probe_mtproto(*, attempts: int = 2, pause: float = 1.0) -> tuple[bool, str]:
    """Return (ok, detail). detail empty when ok."""
    if not user_session_ready():
        return False, "Telethon session is not configured"
    last = ""
    for attempt in range(max(1, attempts)):
        client = _client_factory()
        try:
            client.connect()
            if client.is_connected() and client.is_user_authorized():
                return True, ""
            if not client.is_connected():
                last = "Telethon connect failed"
            else:
                last = "Telethon session is not authorized"
        except Exception as exc:  # noqa: BLE001
            last = format_mtproto_error(exc)
        finally:
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        if attempt + 1 < attempts and pause > 0:
            time.sleep(pause)
    return False, last or "Telethon connect failed"


def with_mtproto_retries(action: Callable[[], T], *, attempts: int = 3, pause: float = 1.5) -> T:
    last_exc: BaseException | None = None
    for attempt in range(max(1, attempts)):
        try:
            return action()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            name = exc.__class__.__name__
            text = str(exc)
            transient = (
                "IncompleteReadError" in name
                or "146 bytes read" in text
                or "Server closed the connection" in text
            )
            if not transient or attempt + 1 >= attempts:
                raise
            time.sleep(pause)
    assert last_exc is not None
    raise last_exc


def run_connected(action: Callable[..., T], *args, **kwargs) -> T:
    """Connect Telethon, run action(client, *args, **kwargs), disconnect."""

    def _once() -> T:
        client = _client_factory()
        try:
            client.connect()
            if not client.is_connected():
                raise RuntimeError("Telethon connect failed")
            if not client.is_user_authorized():
                raise RuntimeError("Telethon session is not authorized")
            return action(client, *args, **kwargs)
        finally:
            client.disconnect()

    return with_mtproto_retries(_once)
