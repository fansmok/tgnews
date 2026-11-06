from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from newsagent.runtime import iso, parse_iso

MSK = ZoneInfo("Europe/Moscow")
TIME_LINE = re.compile(
    r"^(\d{1,2})[:.-](\d{2})(?:\s+(.*))?$",
    re.IGNORECASE,
)
DATE_IN_TEXT = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?(?!\d)")


def is_broadcast(text: str) -> bool:
    low = (text or "").lower()
    return any(kw in low for kw in ("трансл", "транс"))


def _lines(text: str) -> list[str]:
    cleaned = text.replace("\xa0", " ")
    return [line.strip() for line in cleaned.splitlines() if line.strip()]


def looks_like_ad_post(text: str) -> bool:
    lines = _lines(text)
    if not lines:
        return False
    lowered = text.lower()
    if any(phrase in lowered for phrase in ("без рекламы", "рекламы нет", "отмена рекламы")):
        return True
    return any(TIME_LINE.match(line) for line in lines)


def _target_date(lines: list[str], message_dt: datetime):
    head = " ".join(lines[:3]).lower()
    base = message_dt.astimezone(MSK).date()
    if "завтра" in head:
        return base + timedelta(days=1)
    match = DATE_IN_TEXT.search(head)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year_raw = match.group(3)
        year = base.year if not year_raw else int(year_raw)
        if year < 100:
            year += 2000
        return base.replace(year=year, month=month, day=day)
    return base


def parse_ad_post(text: str, message_dt: datetime) -> dict | None:
    if not looks_like_ad_post(text):
        return None
    lines = _lines(text)
    target = _target_date(lines, message_dt)
    lowered = "\n".join(lines).lower()
    cancelled = any(phrase in lowered for phrase in ("без рекламы", "рекламы нет", "отмена рекламы"))
    slots: list[datetime] = []
    items: list[dict] = []
    bare_broadcast = any(is_broadcast(line) and not TIME_LINE.match(line) for line in lines)
    if not cancelled:
        for line in lines:
            match = TIME_LINE.match(line)
            if not match:
                continue
            hour = int(match.group(1))
            minute = int(match.group(2))
            if hour > 23 or minute > 59:
                continue
            rest = match.group(3) or ""
            kind = "broadcast" if is_broadcast(rest) or (bare_broadcast and not rest.strip()) else "regular"
            moment = datetime(target.year, target.month, target.day, hour, minute, tzinfo=MSK)
            slots.append(moment)
            items.append({"time": iso(moment), "kind": kind, "label": line})
    unique_slots = sorted(set(slots))
    unique_items_map = {}
    for item in items:
        t = item["time"]
        if t not in unique_items_map or item["kind"] == "broadcast":
            unique_items_map[t] = item
    unique_items = [unique_items_map[t] for t in sorted(unique_items_map)]
    return {
        "target_date": target.isoformat(),
        "cancelled": cancelled and not unique_slots,
        "message_at": iso(message_dt),
        "slots": [iso(item) for item in unique_slots],
        "items": unique_items,
        "raw": text.strip(),
    }


def select_ad_entries(messages: list[dict]) -> list[dict]:
    """messages: newest first, each {text, message_at}. Returns [{'time': iso, 'kind': ...}]"""
    newest_by_date: dict[str, dict] = {}
    for message in messages:
        parsed = parse_ad_post(message["text"], message["message_at"])
        if not parsed:
            continue
        newest_by_date.setdefault(parsed["target_date"], parsed)
    items_map: dict[str, dict] = {}
    for parsed in newest_by_date.values():
        if parsed["cancelled"]:
            continue
        for it in parsed.get("items") or []:
            t = it["time"]
            if t not in items_map or it.get("kind") == "broadcast":
                items_map[t] = {"time": t, "kind": it.get("kind", "regular")}
    return [items_map[k] for k in sorted(items_map)]


def combine_ad_messages(channel_messages: list[dict], inbox_messages: list[dict]) -> list[dict]:
    """Канал и только что пришедший пост. Сверху самый новый, его расписание и берётся."""
    rows = []
    for message in [*inbox_messages, *channel_messages]:
        text = str(message.get("text") or "").strip()
        moment = message.get("message_at")
        if not text or moment is None:
            continue
        rows.append({"text": text, "message_at": moment})
    rows.sort(key=lambda item: item["message_at"], reverse=True)
    return rows


def _coerce_moment(raw, now: datetime) -> datetime:
    if raw is None or raw == "":
        return now
    if isinstance(raw, (int, float)) or (isinstance(raw, str) and raw.strip().isdigit()):
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)
    return parse_iso(str(raw))


def payload_from_body(raw: str) -> dict | None:
    """Тело вебхука — текст поста как в канале. JSON с полем text тоже принимается."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"text": raw}
    if isinstance(payload, str) and payload.strip():
        return {"text": payload.strip()}
    if isinstance(payload, dict):
        return payload
    return {"text": raw}


def message_from_webhook(payload: dict, now: datetime) -> dict | None:
    """Текст поста из тела вебхука Make. Время строки расписания дальше считается московским."""
    post = payload.get("channel_post") or payload.get("message") or payload
    if not isinstance(post, dict):
        return None
    text = str(post.get("text") or post.get("caption") or "").strip()
    if not text:
        return None
    raw_date = post.get("date") if post.get("date") not in (None, "") else post.get("message_at")
    return {"text": text, "message_at": _coerce_moment(raw_date, now)}


def select_ads(messages: list[dict]) -> list[str]:
    """messages: newest first, each {text, message_at}."""
    newest_by_date: dict[str, dict] = {}
    for message in messages:
        parsed = parse_ad_post(message["text"], message["message_at"])
        if not parsed:
            continue
        newest_by_date.setdefault(parsed["target_date"], parsed)
    slots: list[str] = []
    for parsed in newest_by_date.values():
        if parsed["cancelled"]:
            continue
        slots.extend(parsed["slots"])
    return sorted(set(slots))
