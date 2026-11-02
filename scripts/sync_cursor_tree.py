#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def main() -> int:
    copy_tree(ROOT / "agents", ROOT / ".cursor" / "agents")
    copy_tree(ROOT / "skills", ROOT / ".cursor" / "skills")
    print("synced agents and skills into .cursor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
