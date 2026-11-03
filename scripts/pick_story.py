#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.memory import connect, is_duplicate  # noqa: E402
from newsagent.runtime import iso, load_dotenv, now_msk, read_json, repo_root, write_json  # noqa: E402

BATCH_URLS = "memory/batch-urls.json"


def batch_urls() -> set[str]:
    path = repo_root() / BATCH_URLS
    if not path.exists():
        return set()
    payload = read_json(path)
    if payload.get("date") != now_msk().date().isoformat():
        return set()
    return set(payload.get("urls") or [])


def remember_batch_url(url: str) -> None:
    path = repo_root() / BATCH_URLS
    urls = batch_urls()
    urls.add(url)
    write_json(path, {"date": now_msk().date().isoformat(), "urls": sorted(urls), "updated_at": iso(now_msk())})


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    payload = read_json(run_dir / "candidates.json")
    exclude = set()
    exclude_path = run_dir / "exclude.json"
    if exclude_path.exists():
        exclude = set(read_json(exclude_path).get("urls") or [])
    exclude |= batch_urls()
    conn = connect(repo_root() / "memory" / "news.db")
    skipped = []
    selected = None
    for item in sorted(payload.get("items") or [], key=lambda row: row.get("score", 0), reverse=True):
        if item["url"] in exclude:
            skipped.append({"url": item["url"], "reason": "excluded"})
            continue
        duplicate, reason = is_duplicate(conn, item)
        if duplicate:
            skipped.append({"url": item["url"], "reason": reason})
            continue
        selected = item
        break
    if not selected:
        write_json(
            run_dir / "memory-decision.json",
            {"duplicate": False, "selected_url": None, "reason": "no_fresh_story", "skipped": skipped},
        )
        print("NO_NEWS")
        return 2
    write_json(
        run_dir / "memory-decision.json",
        {"duplicate": False, "selected_url": selected["url"], "reason": "new", "skipped": skipped},
    )
    write_json(run_dir / "story.json", selected)
    remember_batch_url(selected["url"])
    print(f"selected={selected['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
