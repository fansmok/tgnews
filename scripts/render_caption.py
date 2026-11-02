#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.caption import render_post  # noqa: E402
from newsagent.runtime import load_dotenv, read_json, repo_root, write_json  # noqa: E402


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    copy = read_json(run_dir / "copy.json")
    emoji = read_json(run_dir / "emoji.json")
    voice = read_json(run_dir / "voice.json") if (run_dir / "voice.json").exists() else {"comment": None}
    rendered = render_post(
        {
            "title": copy.get("title"),
            "paragraphs": copy.get("paragraphs") or [],
            "bold_spans": copy.get("bold_spans") or [],
            "quote": copy.get("quote"),
            "comment": voice.get("comment"),
            "title_emoji": emoji.get("title_emoji"),
            "paragraph_emoji": emoji.get("paragraph_emoji") or [],
        }
    )
    (run_dir / "caption.html").write_text(rendered["html"], encoding="utf-8")
    write_json(run_dir / "caption.json", rendered)
    print(f"visible={rendered['visible_length']}")
    return 0 if rendered["visible_length"] <= 1000 else 1


if __name__ == "__main__":
    raise SystemExit(main())
