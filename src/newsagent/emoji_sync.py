from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from newsagent.runtime import repo_root

UNICODE_TAGS = {
    "⚽": "football",
    "⚽️": "football",
    "🏆": "trophy",
    "🥇": "trophy",
    "👑": "trophy",
    "🥅": "goal",
    "🔴": "red-card",
    "🟥": "red-card",
    "🟨": "yellow-card",
    "💰": "transfer",
    "💸": "transfer",
    "💵": "transfer",
    "💱": "transfer",
    "🔄": "transfer",
    "✏️": "contract",
    "🤕": "injury",
    "✍️": "contract",
    "🎙️": "quote",
    "🎙": "quote",
    "🎤": "quote",
    "💬": "quote",
    "📊": "record",
    "📈": "record",
    "🚨": "conflict",
    "⚡️": "news",
    "⚡": "news",
    "❗️": "news",
    "⚠️": "conflict",
    "🚫": "conflict",
    "⛔️": "conflict",
    "🤫": "news",
    "👀": "news",
    "🔥": "news",
    "📌": "news",
    "🆚": "football",
    "🏟": "football",
    "🤡": "football",
    "🎉": "football",
}

ALLOWED_PACKS = (
    "RestrictedEmoji",
    "foot_flags_by_fStikBot",
    "NewsEmoji",
    "FC_logos",
)


def load_hints() -> dict[str, str]:
    path = repo_root() / "shared" / "emoji-tag-hints.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {key.lower().replace("ё", "е"): value for key, value in raw.items()}


def load_logo_tags() -> dict[str, str]:
    path = repo_root() / "shared" / "fc-logo-tags.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): value for key, value in raw.items()}


def tags_for(keywords: list[str], fallback: str, hints: dict[str, str]) -> list[str]:
    blob = " ".join(keywords).lower().replace("ё", "е")
    tags: set[str] = set()
    for needle, tag in sorted(hints.items(), key=lambda item: len(item[0]), reverse=True):
        if needle and needle in blob:
            tags.add(tag)
    generic = UNICODE_TAGS.get(fallback)
    if generic:
        tags.add(generic)
    if not tags:
        tags.add("football")
    return sorted(tags)


def is_flag(fallback: str) -> bool:
    return any(0x1F1E6 <= ord(char) <= 0x1F1FF or 0xE0061 <= ord(char) <= 0xE007F for char in fallback)


def items_from_bot_set(payload: dict, set_name: str, hints: dict[str, str]) -> list[dict]:
    logo_tags = load_logo_tags()
    items = []
    for sticker in payload.get("stickers") or []:
        emoji_id = str(sticker.get("custom_emoji_id") or "")
        if not emoji_id.isdigit():
            continue
        fallback = sticker.get("emoji") or "⚽"
        if set_name == "FC_logos":
            tags = [logo_tags[emoji_id]] if emoji_id in logo_tags else ["club-logo"]
        elif is_flag(fallback):
            tags = ["flag"]
        else:
            tags = tags_for([], fallback, hints)
        items.append(
            {
                "custom_emoji_id": emoji_id,
                "fallback": fallback,
                "set_name": set_name,
                "keywords": [],
                "tags": tags,
            }
        )
    return items


def fetch_bot_set(token: str, name: str) -> dict:
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/getStickerSet",
        json={"name": name},
        timeout=40,
    )
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description") or f"getStickerSet failed for {name}")
    return payload["result"]


def sync_catalog(token: str, packs: list[str]) -> dict:
    hints = load_hints()
    items: list[dict] = []
    errors: list[str] = []
    for name in packs:
        if name not in ALLOWED_PACKS:
            errors.append(f"{name}: pack is not allowed")
            continue
        try:
            payload = fetch_bot_set(token, name)
        except Exception as exc:  # noqa: BLE001 - one pack must not abort the rest
            errors.append(f"{name}: {exc}")
            continue
        items.extend(items_from_bot_set(payload, name, hints))
    return {"packs": packs, "items": items, "errors": errors}


def catalog_path() -> Path:
    return repo_root() / "shared" / "emoji-catalog.json"


def token_from_env() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return token
