#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.branding import boxes_overlap  # noqa: E402
from newsagent.runtime import read_json, write_json  # noqa: E402


def review(run_dir: Path) -> dict:
    design = read_json(run_dir / "design.json")
    image = Image.open(run_dir / design["file"]).convert("RGB")
    issues = []
    width, height = image.size
    if (width, height) != (design.get("width"), design.get("height")):
        issues.append("file size does not match design.json")
    slots = {key: tuple(value) for key, value in (design.get("slots") or {}).items()}
    for name, box in slots.items():
        x, y, w, h = box
        if w < 8 or h < 8:
            issues.append(f"{name} is too small")
        if x < 0 or y < 0 or x + w > width + 1 or y + h > height + 1:
            issues.append(f"{name} leaves the frame")
    if "badge" in slots and "logo" in slots and boxes_overlap(slots["badge"], slots["logo"]):
        issues.append("badge overlaps the logo")
    if "headline" in slots and "logo" in slots and boxes_overlap(slots["headline"], slots["logo"]):
        issues.append("headline overlaps the logo")
    if "headline" in slots and "footer" in slots and boxes_overlap(slots["headline"], slots["footer"]):
        issues.append("footer overlaps the headline")
    photo = slots.get("photo")
    if photo:
        cx = photo[0] + photo[2] // 2
        cy = photo[1] + int(photo[3] * 0.35)
        pixel = image.getpixel((min(cx, width - 1), min(cy, height - 1)))
        if pixel[1] > 80 and pixel[0] < 40 and pixel[2] < 40:
            issues.append("photo window looks empty")
    verdict = "PASS" if not issues else "REWORK"
    return {"verdict": verdict, "target": "" if verdict == "PASS" else "fn-design", "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    payload = review(run_dir)
    write_json(run_dir / "photo-review.json", payload)
    print(f"photo_review={payload['verdict']}")
    return 0 if payload["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
