#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.runtime import iso, load_dotenv, now_msk, repo_root, write_json  # noqa: E402


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    args = parser.parse_args()
    root = repo_root()
    now = now_msk()
    run_id = args.run_id or now.strftime("R-%Y%m%d-%H%M%S")
    run_dir = root / "memory" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    context = {
        "run_id": run_id,
        "started_at": iso(now),
        "timezone": "Europe/Moscow",
        "publish_allow": os.environ.get("PUBLISH_ALLOW", "no").strip().lower() == "yes",
        "publish_backend": os.environ.get("PUBLISH_BACKEND", "bot").strip() or "bot",
        "run_dir": str(run_dir.relative_to(root)),
    }
    write_json(run_dir / "context.json", context)
    template = (root / "shared" / "pipeline-handoff.template.md").read_text(encoding="utf-8")
    handoff = template.replace("{{run_id}}", run_id).replace("{{run_dir}}", context["run_dir"]).replace(
        "{{started_at}}", context["started_at"]
    )
    target = root / ".cursor" / "football-news-handoff.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(handoff, encoding="utf-8")
    print(f"run_id={run_id}")
    print(f"run_dir={context['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
