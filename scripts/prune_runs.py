#!/usr/bin/env python3
"""Удаляет тяжёлые артефакты старых выпусков, не затрагивая news.db."""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.runtime import now_msk, parse_iso, read_json, repo_root  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--keep", type=int, default=5)
    args = parser.parse_args()
    runs = repo_root() / "memory" / "runs"
    rows: list[tuple[Path, object]] = []
    for folder in runs.iterdir():
        context = folder / "context.json"
        if not folder.is_dir() or not context.exists():
            continue
        try:
            started = parse_iso(read_json(context)["started_at"])
        except Exception:
            continue
        rows.append((folder, started))
    rows.sort(key=lambda row: row[1], reverse=True)
    protected = {folder for folder, _started in rows[: max(0, args.keep)]}
    cutoff = now_msk() - timedelta(days=max(1, args.days))
    removed = 0
    freed = 0
    for folder, started in rows:
        if folder in protected or started >= cutoff:
            continue
        freed += sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
        shutil.rmtree(folder)
        removed += 1
    print(f"removed={removed} freed_bytes={freed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
