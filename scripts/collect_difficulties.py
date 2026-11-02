#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.difficulties import collect_difficulties  # noqa: E402
from newsagent.runtime import repo_root  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--run-dir":
        print("usage: collect_difficulties.py --run-dir <dir>")
        return 1
    run_dir = Path(sys.argv[2])
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    payload = collect_difficulties(run_dir)
    print(f"reports={payload['reports']} difficulties={payload['difficulties']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
