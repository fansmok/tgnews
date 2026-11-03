#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.photos import acceptable, extension, extract_og_image  # noqa: E402
from newsagent.runtime import load_dotenv, read_json, repo_root, write_json  # noqa: E402


def download(client: httpx.Client, url: str) -> bytes | None:
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    return response.content


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    story = read_json(run_dir / "story.json")
    urls = list(story.get("image_urls") or [])
    headers = {"User-Agent": "Mozilla/5.0"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=25) as client:
        if story.get("url") and not (story.get("source_kind") == "telegram" and urls):
            page = download(client, story["url"])
            if page:
                (run_dir / "source-page.html").write_bytes(page)
                og = extract_og_image(story["url"], page.decode("utf-8", "replace"))
                if og and og not in urls:
                    urls.append(og)
        for url in urls:
            payload = download(client, url)
            if not payload:
                continue
            ok, reason, width, height = acceptable(url, payload)
            if not ok:
                continue
            filename = f"photo.{extension(payload)}"
            (run_dir / filename).write_bytes(payload)
            write_json(
                run_dir / "photo.json",
                {"status": "ok", "file": filename, "source_url": url, "width": width, "height": height},
            )
            print(f"photo={filename} {width}x{height}")
            return 0
    write_json(run_dir / "photo.json", {"status": "fail", "file": "", "detail": "no acceptable image"})
    print("NO_PHOTO")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
