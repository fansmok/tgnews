#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.gitfix import commit_and_push  # noqa: E402
from newsagent.runtime import repo_root, write_json  # noqa: E402


def main() -> int:
    message = "fix: записать трудности футбольного пайплайна"
    if "--message" in sys.argv:
        message = sys.argv[sys.argv.index("--message") + 1]
    no_push = "--no-push" in sys.argv
    result = commit_and_push(repo_root(), message, push=not no_push)
    write_json(repo_root() / "memory" / "last-push.json", result)
    print(f"status={result['status']} push={result.get('push', '')}")
    if result["status"] in {"refused", "error"}:
        return 1
    if result["status"] == "needs-human":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
