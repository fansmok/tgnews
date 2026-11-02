#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.memory import connect, occupied_slots  # noqa: E402
from newsagent.runtime import iso, load_dotenv, now_msk, parse_iso, read_json, repo_root, write_json  # noqa: E402
from newsagent.schedule import blackout_intervals, next_publish  # noqa: E402


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--now")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    ads_path = run_dir / "ads.json"
    if not ads_path.exists():
        print("ERROR ads.json missing")
        return 1
    ads_payload = read_json(ads_path)
    if ads_payload.get("status") != "ok":
        print("ERROR ads status is not ok; refuse to plan a slot")
        return 1
    now = parse_iso(args.now) if args.now else now_msk()
    ads = ads_payload.get("items") or [parse_iso(item) for item in ads_payload.get("slots") or []]
    conn = connect(repo_root() / "memory" / "news.db")
    plan = next_publish(now, ads, occupied_slots(conn))
    blackouts = [
        {"start": iso(start), "end": iso(end)}
        for start, end in blackout_intervals(ads)
    ]
    if not plan:
        payload = {"status": "no_slot", "prepare": False, "blackouts": blackouts, "now": iso(now)}
        write_json(run_dir / "slot-plan.json", payload)
        print("no_slot")
        return 2
    payload = {
        "status": "ok",
        "publish_at": iso(plan["publish_at"]),
        "reason": plan["reason"],
        "prepare": plan["prepare"],
        "seconds_until": plan["seconds_until"],
        "in_blackout_now": plan["in_blackout_now"],
        "blackouts": blackouts,
        "now": iso(now),
    }
    write_json(run_dir / "slot-plan.json", payload)
    print(f"publish_at={payload['publish_at']} reason={payload['reason']} prepare={payload['prepare']}")
    return 0 if plan["prepare"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
