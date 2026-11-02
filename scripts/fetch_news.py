#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.feeds import dedupe_batch, parse_feed  # noqa: E402
from newsagent.lexicon import load_lexicon  # noqa: E402
from newsagent.runtime import load_dotenv, now_msk, repo_root, write_json  # noqa: E402

CACHE_TTL = 10 * 60


def fetch_payloads(sources: dict) -> tuple[dict[str, bytes], list[str]]:
    cache_dir = repo_root() / "memory" / "feed-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, bytes] = {}
    errors: list[str] = []
    stale: list[dict] = []
    for source in sources["feeds"]:
        cache_path = cache_dir / f"{source['id']}.xml"
        if cache_path.exists() and time.time() - cache_path.stat().st_mtime < CACHE_TTL:
            payloads[source["id"]] = cache_path.read_bytes()
        else:
            stale.append(source)

    def fetch(source: dict) -> tuple[dict, bytes]:
        response = httpx.get(
            source["url"],
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
            timeout=25,
        )
        response.raise_for_status()
        return source, response.content

    with ThreadPoolExecutor(max_workers=min(7, len(stale) or 1)) as pool:
        futures = {pool.submit(fetch, source): source for source in stale}
        for future in as_completed(futures):
            source = futures[future]
            try:
                _source, payload = future.result()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{source['id']}: {exc.__class__.__name__}")
                continue
            payloads[source["id"]] = payload
            (cache_dir / f"{source['id']}.xml").write_bytes(payload)
    return payloads, errors


def collect(sources: dict, payloads: dict[str, bytes], now, max_age: float) -> list[dict]:
    items: list[dict] = []
    lexicon = load_lexicon()
    for source in sources["feeds"]:
        payload = payloads.get(source["id"])
        if payload:
            items.extend(parse_feed(payload, source, now, max_age, lexicon=lexicon))
    return items


def main() -> int:
    load_dotenv()
    if len(sys.argv) != 3 or sys.argv[1] != "--run-dir":
        print("usage: fetch_news.py --run-dir <dir>")
        return 1
    run_dir = Path(sys.argv[2])
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    sources = json.loads((repo_root() / "shared" / "sources.json").read_text(encoding="utf-8"))
    now = now_msk()
    payloads, errors = fetch_payloads(sources)
    items = collect(sources, payloads, now, float(sources["max_age_hours"]))
    if not items:
        items = collect(sources, payloads, now, float(sources["expand_age_hours"]))
    items = dedupe_batch(items)[:30]
    write_json(run_dir / "candidates.json", {"items": items, "errors": errors})
    print(f"candidates={len(items)} feed_errors={len(errors)}")
    if not items and errors and len(errors) >= len(sources["feeds"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
