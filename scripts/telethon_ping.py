#!/usr/bin/env python3
"""Проверка user-сессии Telethon: без неё нет отложки и premium custom emoji."""
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
    from newsagent.telegram_user import connect_user

    try:
        client = connect_user()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR telethon {exc.__class__.__name__}: {str(exc)[:200]}")
        return 1
    try:
        me = client.get_me()
        transport = type(client._sender._connection).__name__ if client._sender._connection else "?"
        print(f"OK telethon user_id={me.id} premium={bool(me.premium)} transport={transport}")
        return 0
    finally:
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
