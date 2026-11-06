#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.branding import pick_template  # noqa: E402
from newsagent.custom_emoji import pick_custom  # noqa: E402
from newsagent.emoji_sync import catalog_path  # noqa: E402
from newsagent.lexicon import merge_story_clubs  # noqa: E402
from newsagent.runtime import read_json, repo_root, write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    story = read_json(run_dir / "story.json")
    copy = read_json(run_dir / "copy.json") if (run_dir / "copy.json").exists() else {}
    copy_text = " ".join([copy.get("title") or "", *(copy.get("paragraphs") or [])])
    story = {
        **story,
        "clubs": merge_story_clubs(
            story.get("clubs") or [],
            story.get("title") or "",
            story.get("summary") or "",
            copy.get("source_text") or "",
            copy_text,
        ),
    }
    template = pick_template(story, copy)
    catalog = read_json(catalog_path())
    try:
        payload = pick_custom(story, copy, template, catalog)
    except LookupError as exc:
        print(f"ERROR {exc}")
        return 1
    write_json(run_dir / "emoji.json", payload)
    if story["clubs"]:
        write_json(run_dir / "story.json", story)
    chosen = payload["title_emoji"]
    chosen = chosen if isinstance(chosen, list) else [chosen]
    print("emoji=" + " ".join(item["fallback"] for item in chosen) + f" pack={chosen[0]['set_name']} topic={chosen[0]['tags'][0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
