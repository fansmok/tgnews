#!/usr/bin/env python3
"""Публикует готовые run_dir дневной пачки (critic PASS), если publish ещё не удался.

Нужен PUBLISH_BACKEND=user: Bot API в канале игнорирует schedule_date.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.runtime import load_dotenv, read_json, repo_root  # noqa: E402


def ready_runs(root: Path) -> list[Path]:
    runs_root = root / "memory" / "runs"
    if not runs_root.exists():
        return []
    ready: list[Path] = []
    for run_dir in sorted(runs_root.iterdir()):
        if not run_dir.is_dir():
            continue
        plan = run_dir / "slot-plan.json"
        critic = run_dir / "critic.json"
        result = run_dir / "publish-result.json"
        if not plan.exists() or not critic.exists():
            continue
        if read_json(critic).get("verdict") != "PASS":
            continue
        if result.exists() and read_json(result).get("status") in {"sent", "scheduled"}:
            continue
        if not read_json(plan).get("batch_defer"):
            continue
        ready.append(run_dir)
    return ready


def main() -> int:
    load_dotenv()
    root = repo_root()
    runs = ready_runs(root)
    if not runs:
        print("nothing_to_publish")
        return 0
    code = 0
    for run_dir in runs:
        rel = run_dir.relative_to(root)
        proc = subprocess.run(
            [sys.executable, str(root / "scripts" / "pipeline.py"), "publish", "--run-dir", str(rel)],
            cwd=str(root),
        )
        print(f"{rel} exit={proc.returncode}")
        if proc.returncode != 0:
            code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
