"""Новости из публичных Telegram-каналов через веб-превью t.me/s/<канал>.

Превью отдаёт текст, время и фото поста без MTProto, поэтому статьи не скачиваются,
а копирайтер получает уже короткий текст поста.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from newsagent.copytext import strip_emoji, list_teaser_without_names
from newsagent.lexicon import classify, event_key, find_ids, load_lexicon
from newsagent.memory import jaccard, person_skeletons, title_norm, _same_person
from newsagent.runtime import iso, parse_iso, read_json, repo_root, write_json

MSK = ZoneInfo("Europe/Moscow")
PREVIEW = "https://t.me/s/{username}"
CACHE_TTL = 10 * 60
MAX_PAGES = 6
MIN_TEXT = 40
ACTION_BONUS = {"transfer": 6, "injury": 5, "sack": 5, "contract": 4, "red-card": 3, "debut": 2}

AD_LINE = re.compile(
    r"(?<!\w)(?:кф|кэфф?|экспресс\w*|ставк\w*|став(?:ь|ьте|им|лю)|букмекер\w*|фрибет\w*|промокод\w*"
    r"|казино|депозит\w*|разда(?:м|ю|ём|ем)|vip|вип|erid|реклама|в лс|пиши(?:те)? мне|переходи(?:те)?"
    r"|жми(?:те)?|вас упомянул\w*|забрать\s+(?:деньги|этот|экспресс|бонус|приз)\w*)(?!\w)",
    re.IGNORECASE,
)
SIGNATURE_LINE = re.compile(r"^[\s|]*(?:наши каналы|мы в max|подпис\w*|ссылка:?\s*$)", re.IGNORECASE)
URL_LINE = re.compile(r"^\s*(?:https?://|t\.me/)\S+\s*$", re.IGNORECASE)
DASH_LINE = re.compile(r"^\s*[—–-]\s*\S")
SCORE = re.compile(r"(?<![\d:.,])(\d{1,2})\s?:\s?(\d{1,2})(?![\d:])")
RESULT = re.compile(
    r"(?<!\w)(?:обыграл\w*|разгромил\w*|победил[аи]?|проиграл[аи]?|уступил[аи]?|сыграл[аи]? вничью"
    r"|одержал[аи]? победу|вырвал[аи]? победу|камбэк\w*|итоги тура|хет-трик\w*|оформил[аи]? дубль)(?!\w)",
    re.IGNORECASE,
)
DAY_WORD = re.compile(r"(?<!\w)(?:сегодня|сегодняшн\w*|этим вечером|завтра|завтрашн\w*)(?!\w)", re.IGNORECASE)
MATCH_WORD = re.compile(r"(?<!\w)(?:матч\w*|игр[аеуы]|встреч\w*|победит|сыграет|против|соперник\w*)(?!\w)", re.IGNORECASE)


def has_score(text: str) -> bool:
    for match in SCORE.finditer(text):
        left, right = match.groups()
        if len(right) == 2 and (right[0] == "0" or int(right) > 15):
            continue
        if int(left) > 15:
            continue
        return True
    return False


def stale_reason(text: str) -> str:
    """Счета, итоги и анонсы «сегодня» к моменту выхода поста уже неактуальны."""
    if has_score(text):
        return "score"
    if RESULT.search(text):
        return "result"
    if DAY_WORD.search(text) and MATCH_WORD.search(text):
        return "today_match"
    return ""


def _text_of(node) -> str:
    for emoji in node.select("tg-emoji, i.emoji"):
        emoji.decompose()
    for br in node.find_all("br"):
        br.replace_with("\n")
    lines = [strip_emoji(line) for line in node.get_text("").split("\n")]
    return "\n".join(line.strip() for line in lines)


def _image_urls(node) -> list[str]:
    found: list[str] = []
    for item in node.select(".tgme_widget_message_photo_wrap, .tgme_widget_message_video_thumb"):
        match = re.search(r"url\(['\"]?([^'\")]+)", item.get("style") or "")
        if not match:
            continue
        url = match.group(1)
        if url.startswith("//"):
            url = "https:" + url
        if url not in found:
            found.append(url)
    return found


def parse_preview(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    messages = []
    for wrap in soup.select(".tgme_widget_message_wrap"):
        node = wrap.select_one(".tgme_widget_message")
        moment = wrap.select_one(".tgme_widget_message_date time")
        if node is None or moment is None or not moment.get("datetime") or not node.get("data-post"):
            continue
        text_node = node.select_one(".tgme_widget_message_text")
        messages.append(
            {
                "post": node["data-post"],
                "id": int(node["data-post"].rsplit("/", 1)[-1]),
                "date": moment["datetime"],
                "text": _text_of(text_node) if text_node else "",
                "image_urls": _image_urls(node),
                "forwarded": node.select_one(".tgme_widget_message_forwarded_from") is not None,
            }
        )
    return messages


def clean_post(text: str, strip_lines: list[str] | None = None) -> tuple[str, str]:
    """Убирает подпись канала, опрос и рекламный хвост. Пустой текст и причина — пост не годится."""
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    blocked = {item.strip().lower() for item in strip_lines or []}
    lines = [
        line
        for line in lines
        if line.lower() not in blocked and not SIGNATURE_LINE.search(line) and not URL_LINE.match(line)
    ]
    for index, line in enumerate(lines):
        if AD_LINE.search(line):
            if len(" ".join(lines[:index])) < 60:
                return "", "ad"
            lines = lines[:index]
            break
    options = 0
    while lines and DASH_LINE.match(lines[-1]):
        lines.pop()
        options += 1
    if options and lines and lines[-1].endswith("?"):
        lines.pop()
    cleaned = "\n".join(lines).strip()
    if len(cleaned) < MIN_TEXT:
        return "", "short"
    return cleaned, ""


def _get(username: str, before: int | None) -> str:
    response = httpx.get(
        PREVIEW.format(username=username),
        params={"before": before} if before else None,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=25,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.text


def fetch_channel(username: str, since: datetime, fetch=_get) -> list[dict]:
    """Посты канала начиная с since; превью отдаёт по 20 штук, листаем через ?before=."""
    collected: dict[int, dict] = {}
    before = None
    for _ in range(MAX_PAGES):
        page = parse_preview(fetch(username, before))
        if not page:
            break
        for message in page:
            collected[message["id"]] = message
        oldest = min(page, key=lambda item: item["id"])
        if parse_iso(oldest["date"]) < since or oldest["id"] <= 1:
            break
        before = oldest["id"]
    return sorted(collected.values(), key=lambda item: item["id"])


def cached_channel(username: str, since: datetime) -> list[dict]:
    path = repo_root() / "memory" / "feed-cache" / f"tg-{username}.json"
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL:
        payload = read_json(path)
        if payload.get("since") and parse_iso(payload["since"]) <= since:
            return payload.get("messages") or []
    messages = fetch_channel(username, since)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {"since": iso(since), "messages": messages})
    return messages


def story_from_message(message: dict, channel: dict, now: datetime, lexicon: dict) -> tuple[dict | None, str]:
    if message.get("forwarded"):
        return None, "forwarded"
    if not message.get("image_urls"):
        return None, "no_image"
    text, reason = clean_post(message.get("text") or "", channel.get("strip_lines"))
    if not text:
        return None, reason
    lines = [line for line in text.split("\n") if line.strip()]
    title_line = lines[0] if lines else ""
    body_lines = lines[1:]
    if list_teaser_without_names(title_line, body_lines, ""):
        return None, "list_no_names"
    stale = stale_reason(text)
    if stale:
        return None, stale
    title, _, summary = text.partition("\n")
    verdict = classify(title, summary, lexicon, "")
    if not verdict["keep"]:
        return None, verdict["drop_reason"]
    if verdict["action"] in {"result", "lineup"}:
        return None, verdict["action"]
    clubs = find_ids(title, lexicon["clubs"]) or verdict["clubs"][:2]
    published = parse_iso(message["date"])
    age = (now.astimezone(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 3600
    day = published.astimezone(MSK).date().isoformat()
    action = verdict["action"]
    score = (
        channel.get("weight", 5)
        + verdict["tier"] * 2
        + max(0, min(8, int(8 - age / 3)))
        + ACTION_BONUS.get(action, 0)
    )
    username = channel["username"]
    return {
        "source_id": f"tg:{username}",
        "source_kind": "telegram",
        "source_weight": channel.get("weight", 5),
        "lang": "ru",
        "title": title.strip()[:200],
        "summary": summary.strip()[:2000],
        "url": f"https://t.me/{message['post']}",
        "published_at": iso(published),
        "age_hours": round(age, 2),
        "image_urls": message["image_urls"],
        "clubs": clubs,
        "competitions": verdict["competitions"],
        "action": action,
        "tier": verdict["tier"],
        "event_key": event_key(day, action, clubs),
        "score": score,
    }, ""


def same_story(left: dict, right: dict) -> bool:
    """Один сюжет в разных каналах: общие имена героев или близкий текст."""
    left_text = f"{left['title']} {left['summary'][:300]}"
    right_text = f"{right['title']} {right['summary'][:300]}"
    overlap = jaccard(title_norm(left_text), title_norm(right_text))
    if overlap >= 0.35:
        return True
    left_names = person_skeletons(left_text)
    right_names = person_skeletons(right_text)
    shared = sum(1 for name in left_names if _same_person({name}, right_names))
    return shared >= 2 or (shared >= 1 and overlap >= 0.15)


def dedupe_stories(items: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for item in sorted(items, key=lambda row: row["score"], reverse=True):
        if not any(same_story(item, previous) for previous in kept):
            kept.append(item)
    return kept


def collect_channels(channels: list[dict], now: datetime, hours: float, loader=cached_channel) -> tuple[list[dict], list[str], dict]:
    lexicon = load_lexicon()
    since = now - timedelta(hours=hours)
    items: list[dict] = []
    errors: list[str] = []
    skipped: dict[str, int] = {}
    for channel in channels:
        username = channel["username"]
        try:
            messages = loader(username, since)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"tg:{username}: {exc.__class__.__name__}")
            continue
        for message in messages:
            if parse_iso(message["date"]) < since:
                continue
            story, reason = story_from_message(message, channel, now, lexicon)
            if story is None:
                skipped[reason] = skipped.get(reason, 0) + 1
                continue
            items.append(story)
    return dedupe_stories(items), errors, skipped
