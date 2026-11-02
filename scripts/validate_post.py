#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.checks import machine_check  # noqa: E402
from newsagent.runtime import load_dotenv, read_json, repo_root, write_json  # noqa: E402


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--require-critic", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    report = machine_check(run_dir)
    write_json(run_dir / "machine.json", {key: value for key, value in report.items() if key != "caption"})
    caption = report.get("caption")
    if caption:
        write_json(run_dir / "caption.json", caption)
        (run_dir / "caption.html").write_text(caption["html"], encoding="utf-8")
    critic_ok = True
    if args.require_critic:
        critic_path = run_dir / "critic.json"
        if not critic_path.exists():
            critic_ok = False
            print("critic missing")
        else:
            verdict = read_json(critic_path).get("verdict")
            critic_ok = verdict == "PASS"
            if not critic_ok:
                print(f"critic={verdict}")
    print(f"machine={report['status']}")
    return 0 if report["status"] == "PASS" and critic_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
