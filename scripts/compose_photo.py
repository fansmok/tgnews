#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.branding import brand_spec, compose, pick_template, pillow_footer  # noqa: E402
from newsagent.flux import FluxUnavailable, build_prompt, render_card  # noqa: E402
from newsagent.runtime import load_dotenv, parse_iso, read_json, repo_root, write_json  # noqa: E402


def _facts(story: dict, copy: dict) -> dict:
    paragraphs = copy.get("paragraphs") or []
    summary = paragraphs[0] if paragraphs else (story.get("summary") or "")
    quote = copy.get("quote") or {}
    blob = " ".join(
        part
        for part in (
            copy.get("title") or "",
            summary,
            " ".join(copy.get("bold_spans") or []),
            story.get("title") or "",
        )
        if part
    )
    score = re.search(r"(\d{1,2})\s*[:–\-]\s*(\d{1,2})", blob)
    amount = re.search(r"(\d+(?:[\s\u00a0]\d+)?(?:[,.]\d+)?)\s*(млн|миллион\w*|€|евро|£|\$)", blob, re.I)
    clubs = [item.replace("-", " ").upper() for item in (story.get("clubs") or [])]
    when = ""
    if story.get("published_at"):
        when = parse_iso(story["published_at"]).strftime("%d.%m %H:%M")
    return {
        "summary": summary,
        "quote": quote.get("text") or "",
        "attribution": quote.get("author") or "",
        "home": clubs[0] if clubs else "",
        "away": clubs[1] if len(clubs) > 1 else "",
        "score": f"{score.group(1)} : {score.group(2)}" if score else "",
        "competition": " · ".join(story.get("competitions") or []),
        "when": when,
        "amount": f"{amount.group(1)} {amount.group(2)}" if amount else "",
        "stat_value": (copy.get("bold_spans") or [""])[0],
        "stat_label": summary,
    }


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    story = read_json(run_dir / "story.json")
    photo = read_json(run_dir / "photo.json")
    copy_path = run_dir / "copy.json"
    if not copy_path.exists():
        print("ERROR copy.json is required before design")
        return 1
    copy = read_json(copy_path)
    source = Image.open(run_dir / photo["file"])
    source_width, source_height = source.size
    template = pick_template(story, copy)
    design_path = run_dir / "design.json"
    if design_path.exists():
        previous_design = read_json(design_path)
        forced = str(previous_design.get("template") or "")
        same_story = previous_design.get("story_url") == story.get("url")
        if forced in brand_spec()["templates"] and same_story:
            template = forced
    headline = (copy.get("title") or story.get("title") or "").strip()
    footer = pillow_footer(story)
    facts = _facts(story, copy)
    out = run_dir / "designed.jpg"
    reference = repo_root() / "assets" / "brand" / "reference" / "channel-style.jpg"
    fingerprint = hashlib.sha256()
    fingerprint.update(json.dumps(story, sort_keys=True, ensure_ascii=False).encode())
    fingerprint.update(json.dumps(copy, sort_keys=True, ensure_ascii=False).encode())
    fingerprint.update(template.encode())
    fingerprint.update((run_dir / photo["file"]).read_bytes())
    if reference.exists():
        fingerprint.update(reference.read_bytes())
    input_hash = fingerprint.hexdigest()
    if design_path.exists() and out.exists() and not args.force:
        previous = read_json(design_path)
        if previous.get("status") == "ok" and previous.get("input_hash") == input_hash:
            print(f"reused {previous.get('engine', 'design')} template={template} 600x600")
            return 0
    meta = {
        "template": template,
        "story_url": story.get("url"),
        "size_id": "telegram-600",
        "width": 600,
        "height": 600,
        "scale": 1,
        "input_hash": input_hash,
    }
    try:
        if not reference.exists():
            raise FluxUnavailable("channel style reference is missing")
        flux = render_card(
            run_dir / photo["file"],
            reference,
            build_prompt(story, copy, template, facts),
            out,
        )
        meta["engine"] = flux["model"]
        meta["task_id"] = flux["task_id"]
        meta["resolution"] = flux["resolution"]
    except Exception as exc:  # noqa: BLE001
        plain = ImageOps.fit(source.convert("RGB"), (600, 600), method=Image.Resampling.LANCZOS)
        plain.save(out, quality=92, subsampling=0)
        meta["engine"] = "photo"
        meta["flux_error"] = str(exc)
    meta.update(
        {
            "status": "ok",
            "file": "designed.jpg",
            "source_file": photo["file"],
            "source_width": source_width,
            "source_height": source_height,
        }
    )
    write_json(run_dir / "design.json", meta)
    print(f"designed {meta['size_id']} template={template} {meta['width']}x{meta['height']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
