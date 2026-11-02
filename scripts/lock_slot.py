#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.memory import connect, set_slot_status, try_lock_slot  # noqa: E402
from newsagent.runtime import load_dotenv, parse_iso, read_json, repo_root  # noqa: E402


def run_dir_from(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--status", choices=["skipped", "failed", "scheduled", "sent"])
    args = parser.parse_args()
    run_dir = run_dir_from(args.run_dir)
    context = read_json(run_dir / "context.json")
    plan = read_json(run_dir / "slot-plan.json")
    moment = parse_iso(plan["publish_at"])
    conn = connect(repo_root() / "memory" / "news.db")
    if args.status:
        set_slot_status(conn, moment, args.status, context["run_id"])
        print(args.status)
        return 0
    if not try_lock_slot(conn, moment, context["run_id"]):
        print("SLOT_BUSY")
        return 3
    print("locked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
