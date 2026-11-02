from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from newsagent.lexicon import classify, event_key, load_lexicon
from newsagent.memory import canonical_url, similar, title_norm
from newsagent.runtime import iso


FEATURE = re.compile(r"\b(journey|inside story|who are)\b|гид по", re.IGNORECASE)
SKIP_URL = re.compile(
    r"/sounds/|/podcast|/audio/|youtube\.com|youtu\.be|video\.sports\.ru|sports\.ru/video/",
    re.IGNORECASE,
)
VIDEO_DIGEST = re.compile(r"\b(?:видео[\s-]?дайджест|video[\s-]+digest)\b", re.IGNORECASE)
ACTION_BONUS = {"result": 6, "transfer": 6, "injury": 5, "sack": 5, "red-card": 3}
FRESH_ACTIONS = {"result", "lineup"}
FRESH_SECONDS = 10 * 60
MSK = ZoneInfo("Europe/Moscow")


def _struct_to_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        stamp = calendar.timegm(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(stamp, tz=timezone.utc)


def _entry_dt(entry: dict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = _struct_to_dt(entry.get(key))
        if parsed:
            return parsed
    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def image_urls(entry: dict) -> list[str]:
    found: list[str] = []

    def add(url: str | None) -> None:
        if url and url.startswith("http") and url not in found:
            found.append(url)

    for item in entry.get("media_content") or []:
        add(item.get("url") or item.get("href"))
    for item in entry.get("media_thumbnail") or []:
        add(item.get("url") or item.get("href"))
    for item in entry.get("enclosures") or []:
        mime = (item.get("type") or "").lower()
        href = item.get("href") or item.get("url")
        if mime.startswith("image") or (href and any(href.lower().split("?")[0].endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp"))):
            add(href)
    return found


def parse_feed(payload: bytes | str, source: dict, now: datetime, max_age_hours: float, lexicon: dict | None = None) -> list[dict]:
    lexicon = lexicon or load_lexicon()
    parsed = feedparser.parse(payload)
    items: list[dict] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        if (
            not title
            or not link
            or SKIP_URL.search(link)
            or VIDEO_DIGEST.search(title)
            or VIDEO_DIGEST.search(summary)
        ):
            continue
        published = _entry_dt(entry)
        age = None
        if published is not None:
            age = (now.astimezone(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 3600
            if age < -1:
                continue
        verdict = classify(title, summary, lexicon, link)
        if not verdict["keep"]:
            continue
        same_day = published is None or published.astimezone(MSK).date() == now.astimezone(MSK).date()
        if verdict["action"] in FRESH_ACTIONS:
            if age is None or age * 3600 > FRESH_SECONDS:
                continue
        elif not same_day and (age is not None and age > max(max_age_hours, 24)):
            continue
        day = (published or now).astimezone(MSK).date().isoformat()
        recency = 0 if age is None else max(0, min(8, int(8 - age)))
        feature_penalty = 8 if FEATURE.search(title) else 0
        fresh_bonus = 40 if verdict["action"] in FRESH_ACTIONS else 0
        score = (
            source.get("weight", 1)
            + verdict["tier"] * 2
            + recency
            + ACTION_BONUS.get(verdict["action"], 0)
            + fresh_bonus
            - feature_penalty
        )
        items.append(
            {
                "source_id": source["id"],
                "source_weight": source.get("weight", 1),
                "lang": source.get("lang", ""),
                "title": title,
                "summary": summary[:2000],
                "url": canonical_url(link),
                "published_at": iso(published) if published else "",
                "age_hours": None if age is None else round(age, 2),
                "image_urls": image_urls(entry),
                "clubs": verdict["clubs"],
                "competitions": verdict["competitions"],
                "action": verdict["action"],
                "tier": verdict["tier"],
                "event_key": event_key(day, verdict["action"], verdict["clubs"]),
                "score": score,
            }
        )
    return items


def dedupe_batch(items: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for item in sorted(items, key=lambda row: row["score"], reverse=True):
        norm = title_norm(item["title"])
        duplicate = False
        for previous in kept:
            if item["url"] == previous["url"]:
                duplicate = True
                break
            if similar(norm, title_norm(previous["title"])) >= 0.84:
                duplicate = True
                break
            if item["event_key"] and item["event_key"] == previous["event_key"] and item["action"] == "result":
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    return kept
