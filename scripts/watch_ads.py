#!/usr/bin/env python3
"""Daemon for watching the Telegram ads channel for new messages and triggering runs."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.channels import load_messages, normalize_messages, read_inbox, save_inbox  # noqa: E402
from newsagent.runtime import iso, load_dotenv  # noqa: E402


def check_channel(channel: str) -> bool:
    messages, _reader = load_messages(channel)
    messages = normalize_messages(messages)
    if not messages:
        return False
    known_ids = {item.get("message_id") for item in read_inbox() if item.get("message_id")}
    new_messages = [m for m in messages if m.get("message_id") and m.get("message_id") not in known_ids]
    if new_messages:
        known = {item.get("message_id"): item for item in read_inbox()}
        for item in new_messages:
            known[item.get("message_id")] = {
                "text": item["text"],
                "message_at": iso(item["message_at"]),
                "message_id": item.get("message_id"),
            }
        save_inbox(list(known.values()))
        return True
    return False


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=30, help="Check interval in seconds")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    args = parser.parse_args()

    channel = os.environ.get("ADS_CHANNEL", "").strip()
    if not channel:
        print("[WATCH ADS] ADS_CHANNEL is missing", file=sys.stderr)
        return 1

    print(f"[WATCH ADS] Monitoring channel {channel} (interval: {args.interval}s)...")
    while True:
        try:
            has_new = check_channel(channel)
            if has_new:
                print("[WATCH ADS] New message detected! Triggering pipeline preflight...", flush=True)
                subprocess.run([sys.executable, str(ROOT / "scripts" / "pipeline.py"), "gate"], cwd=str(ROOT))
        except Exception as exc:  # noqa: BLE001
            print(f"[WATCH ADS] Error polling channel: {exc}", file=sys.stderr)

        if args.once:
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
