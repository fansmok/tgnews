#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.difficulties import SecretInReport, report_difficulty  # noqa: E402
from newsagent.runtime import read_json, repo_root  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--status", choices=["none", "difficulty"], required=True)
    parser.add_argument("--severity", default="low")
    parser.add_argument("--category", default="other")
    parser.add_argument("--summary", default="")
    parser.add_argument("--recovered", default="")
    parser.add_argument("--fix", default="")
    parser.add_argument("--files", default="")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    context_path = run_dir / "context.json"
    run_id = read_json(context_path)["run_id"] if context_path.exists() else run_dir.name
    files = [item.strip() for item in args.files.split(",") if item.strip()]
    try:
        payload = report_difficulty(
            run_dir,
            role=args.role,
            run_id=run_id,
            status=args.status,
            severity=args.severity,
            category=args.category,
            summary=args.summary,
            recovered=args.recovered,
            fix=args.fix,
            files=files,
        )
    except SecretInReport as exc:
        print(f"ERROR {exc}")
        return 1
    print(f"status={payload['status']} incident={payload['incident_id'] or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
