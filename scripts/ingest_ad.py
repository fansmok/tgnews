#!/usr/bin/env python3
"""Кладёт пост рекламы из тела вебхука в memory/ads-inbox.json.

Дальше fetch_ads читает этот пост вместе с каналом. Время в строках
расписания — московское, unix date из Telegram только говорит, в какой день пост.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.ads import message_from_webhook  # noqa: E402
from newsagent.channels import read_inbox, save_inbox  # noqa: E402
from newsagent.runtime import iso, load_dotenv, now_msk  # noqa: E402


def main() -> int:
    load_dotenv()
    raw = sys.stdin.read().strip()
    if not raw:
        print("skipped=empty")
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("skipped=bad_json")
        return 0
    if not isinstance(payload, dict):
        print("skipped=bad_json")
        return 0
    item = message_from_webhook(payload, now_msk())
    if not item:
        print("skipped=no_text")
        return 0
    known = [row for row in read_inbox() if row.get("text") != item["text"]]
    known.append(
        {
            "text": item["text"],
            "message_at": item["message_at"],
            "message_id": payload.get("message_id") or (payload.get("channel_post") or {}).get("message_id"),
        }
    )
    save_inbox(known)
    print(f"ingested message_at={iso(item['message_at'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
