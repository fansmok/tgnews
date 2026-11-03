#!/usr/bin/env python3
"""Открывает один слот дневной пачки: свой run_dir и уже известное время отложки."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.runtime import iso, load_dotenv, now_msk, parse_iso, read_json, repo_root, write_json  # noqa: E402


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish-at", required=True)
    parser.add_argument("--reason", default="regular")
    args = parser.parse_args()
    root = repo_root()
    moment = parse_iso(args.publish_at)
    stamp = moment.strftime("%H%M")
    run_id = f"R-{moment.strftime('%Y%m%d')}-{stamp}-{args.reason[:3]}"
    run_dir = root / "memory" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    now = now_msk()
    context = {
        "run_id": run_id,
        "started_at": iso(now),
        "timezone": "Europe/Moscow",
        "publish_allow": os.environ.get("PUBLISH_ALLOW", "no").strip().lower() == "yes",
        "publish_backend": os.environ.get("PUBLISH_BACKEND", "bot").strip() or "bot",
        "run_dir": str(run_dir.relative_to(root)),
    }
    write_json(run_dir / "context.json", context)
    write_json(
        run_dir / "slot-plan.json",
        {
            "status": "ok",
            "publish_at": iso(moment),
            "reason": args.reason,
            "prepare": True,
            "seconds_until": int((moment - now).total_seconds()),
            "in_blackout_now": False,
            "now": iso(now),
        },
    )
    ads_path = root / "memory" / "day-ads.json"
    if ads_path.exists():
        write_json(run_dir / "ads.json", read_json(ads_path))
    else:
        write_json(run_dir / "ads.json", {"status": "ok", "slots": [], "items": []})
    batch_path = root / "memory" / "batch-urls.json"
    urls = []
    if batch_path.exists():
        payload = read_json(batch_path)
        if payload.get("date") == now.date().isoformat():
            urls = payload.get("urls") or []
    write_json(run_dir / "exclude.json", {"urls": urls})
    print(f"run_dir={context['run_dir']}")
    print(f"publish_at={iso(moment)} reason={args.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
