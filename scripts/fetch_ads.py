#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.ads import select_ad_entries, select_ads  # noqa: E402
from newsagent.channels import load_messages, normalize_messages  # noqa: E402
from newsagent.runtime import iso, load_dotenv, now_msk, repo_root, write_json  # noqa: E402


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    channel = os.environ.get("ADS_CHANNEL", "").strip()
    if not channel:
        write_json(run_dir / "ads.json", {"status": "error", "detail": "ADS_CHANNEL is missing", "slots": []})
        print("ERROR ADS_CHANNEL is missing")
        return 1
    try:
        messages, reader = load_messages(channel)
        messages = normalize_messages(messages)
    except Exception as exc:  # noqa: BLE001
        write_json(run_dir / "ads.json", {"status": "error", "detail": str(exc), "slots": []})
        print(f"ERROR {exc}")
        return 1
    slots = select_ads(messages)
    items = select_ad_entries(messages)
    write_json(
        run_dir / "ads.json",
        {
            "status": "ok",
            "reader": reader,
            "fetched_at": iso(now_msk()),
            "slots": slots,
            "items": items,
            "posts_seen": len(messages),
        },
    )
    print(f"ads={len(slots)} reader={reader}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
