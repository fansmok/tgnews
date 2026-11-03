#!/usr/bin/env python3
"""Проверка MTProto-сессии user-аккаунта (нужна для отложки и premium через Telethon)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.runtime import load_dotenv  # noqa: E402


def main() -> int:
    load_dotenv()
    for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_STRING_SESSION"):
        if not os.environ.get(key, "").strip():
            print(f"ERROR missing {key}")
            return 1
    from telethon.sessions import StringSession
    from telethon.sync import TelegramClient

    proxy = os.environ.get("TELEGRAM_PROXY", "").strip()
    proxy_arg = None
    if proxy:
        cleaned = proxy.replace("socks5://", "")
        host, _, port = cleaned.partition(":")
        proxy_arg = ("socks5", host, int(port or "1080"))
    client = TelegramClient(
        StringSession(os.environ["TELEGRAM_STRING_SESSION"]),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"],
        proxy=proxy_arg,
        connection_retries=1,
        auto_reconnect=False,
        timeout=25,
    )
    try:
        client.connect()
        if not client.is_connected():
            print("ERROR telethon connect failed")
            return 1
        me = client.get_me()
        print(f"OK telethon user_id={me.id}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR telethon {exc.__class__.__name__}: {str(exc)[:200]}")
        return 1
    finally:
        if client.is_connected():
            client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
