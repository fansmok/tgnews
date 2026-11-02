#!/usr/bin/env python3
"""Локальный интерактивный логин. Строку сессии нужно сохранить в секрет, не в git."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.runtime import load_dotenv  # noqa: E402


def main() -> int:
    load_dotenv()
    from telethon.sessions import StringSession
    from telethon.sync import TelegramClient

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        print(client.session.save())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
