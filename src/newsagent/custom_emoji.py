from __future__ import annotations

import zlib

from newsagent.emoji_sync import ALLOWED_PACKS

TOPIC_FALLBACKS = {
    "result": ["⚽️", "🏆", "🥅", "🥇"],
    "fixture": ["🆚", "🏟", "🗓", "⏱"],
    "transfer": ["💸", "💵", "💱", "✏️", "🔄"],
    "injury": ["🤕"],
    "sack": ["🚨", "⚡️"],
    "urgent": ["🚨", "⚡️", "❗️"],
    "quote": ["🎙", "🎤", "💬"],
    "stats": ["📊", "📈"],
    "scandal": ["⚠️", "🚫", "⛔️"],
    "insider": ["🤫", "👀"],
    "meme": ["🤡", "🎉", "😄"],
    "main": ["🔥", "📌", "🆕", "⚽️"],
    "trophy": ["🏆", "🥇", "👑"],
}
SET_RANK = {name: index for index, name in enumerate(("NewsEmoji", "foot_flags_by_fStikBot", "RestrictedEmoji", "FC_logos"))}


def _plain(value: str) -> str:
    return (value or "").replace("\ufe0f", "")


def _topic(template: str, story: dict) -> str:
    action = (story or {}).get("action") or ""
    if template == "urgent" and action == "injury":
        return "injury"
    if template == "urgent" and action == "sack":
        return "sack"
    if template in TOPIC_FALLBACKS:
        return template
    return "main"


def _usable(item: dict, story: dict) -> bool:
    if item.get("set_name") not in ALLOWED_PACKS or item.get("set_name") == "FC_logos":
        return False
    tags = set(item.get("tags") or [])
    if "flag" in tags or "club-logo" in tags:
        return bool(tags & set((story or {}).get("clubs") or []))
    return True


def _logo_entry(item: dict, tag: str) -> dict:
    return {
        "custom_emoji_id": item["custom_emoji_id"],
        "fallback": item.get("fallback") or "⚽",
        "tags": [tag],
        "set_name": item["set_name"],
    }


def _tagged_logos(items: list[dict], keys: list[str]) -> list[tuple[dict, str]]:
    chosen: list[tuple[dict, str]] = []
    used: set[str] = set()
    for key in keys:
        pool = [
            item
            for item in items
            if item.get("set_name") == "FC_logos" and key in (item.get("tags") or []) and item.get("custom_emoji_id") not in used
        ]
        if not pool:
            continue
        pool.sort(key=lambda item: item.get("custom_emoji_id") or "")
        chosen.append((pool[0], key))
        used.add(pool[0]["custom_emoji_id"])
    return chosen


def _choose(items: list[dict], symbols: list[str], story: dict, salt: str) -> dict | None:
    wanted = {_plain(symbol) for symbol in symbols}
    matches = [item for item in items if _usable(item, story) and _plain(item.get("fallback") or "") in wanted]
    if not matches:
        return None
    best = min(SET_RANK.get(item.get("set_name"), 9) for item in matches)
    pool = [item for item in matches if SET_RANK.get(item.get("set_name"), 9) == best]
    pool.sort(key=lambda item: item.get("custom_emoji_id") or "")
    index = zlib.crc32(salt.encode()) % len(pool)
    return pool[index]


TOPIC_GATE = {
    "main": "news",
    "stats": "record",
    "fixture": "lineup",
    "urgent": "news",
    "scandal": "conflict",
    "insider": "news",
    "meme": "football",
    "quote": "quote",
    "result": "result",
    "transfer": "transfer",
    "injury": "injury",
    "sack": "sack",
    "trophy": "trophy",
}


def _entry(item: dict, topic: str) -> dict:
    return {
        "custom_emoji_id": item["custom_emoji_id"],
        "fallback": item.get("fallback") or "⚽",
        "tags": [TOPIC_GATE.get(topic, "news")],
        "set_name": item["set_name"],
    }


def _paragraphs(copy: dict, title: dict, second: dict | None) -> list[dict | None]:
    paragraphs = [part for part in (copy or {}).get("paragraphs") or [] if part and part.strip()]
    paragraph_emoji: list[dict | None] = []
    for index, _paragraph in enumerate(paragraphs):
        if index == 0 and second and second["custom_emoji_id"] != title["custom_emoji_id"]:
            paragraph_emoji.append(second)
        else:
            paragraph_emoji.append(None)
    return paragraph_emoji


def pick_custom(story: dict, copy: dict, template: str, catalog: dict) -> dict:
    items = [item for item in catalog.get("items") or [] if item.get("set_name") in ALLOWED_PACKS]
    topic = _topic(template, story)
    symbols = TOPIC_FALLBACKS.get(topic, TOPIC_FALLBACKS["main"])
    url = (story or {}).get("url") or (copy or {}).get("title") or topic
    chosen = _choose(items, symbols, story, url) or _choose(items, TOPIC_FALLBACKS["main"], story, url)
    logos = _tagged_logos(items, list((story or {}).get("clubs") or []))
    if not logos:
        logos = _tagged_logos(items, list((story or {}).get("competitions") or []))
    if logos:
        if len(logos) > 1:
            title = [_logo_entry(*logos[0]), _logo_entry(*logos[1])]
            used_ids = {logos[0][0]["custom_emoji_id"], logos[1][0]["custom_emoji_id"]}
            second = _entry(chosen, topic) if chosen and chosen["custom_emoji_id"] not in used_ids else None
        else:
            title = _logo_entry(*logos[0])
            second = _entry(chosen, topic) if chosen and chosen["custom_emoji_id"] != title["custom_emoji_id"] else None
        paragraphs = [part for part in (copy or {}).get("paragraphs") or [] if part and part.strip()]
        paragraph_emoji: list[dict | None] = []
        for index, _paragraph in enumerate(paragraphs):
            if index == 0 and second:
                paragraph_emoji.append(second)
            else:
                paragraph_emoji.append(None)
        return {"title_emoji": title, "paragraph_emoji": paragraph_emoji}
    if not chosen:
        raise LookupError("no custom emoji in the allowed packs")
    extra = [symbol for symbol in symbols if _plain(symbol) != _plain(chosen.get("fallback") or "")]
    second_item = _choose(items, extra[:1], story, url + "#paragraph") if extra else None
    second_entry = _entry(second_item, topic) if second_item else None
    title = _entry(chosen, topic)
    return {"title_emoji": title, "paragraph_emoji": _paragraphs(copy, title, second_entry)}
