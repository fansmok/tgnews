"""Комментарий держит только реакции Telegram и заменяет их на RestrictedEmoji."""
from __future__ import annotations

import json

from newsagent.runtime import repo_root

ALLOWED_REACTIONS = (
    "❤",
    "👍",
    "👎",
    "🔥",
    "🥰",
    "👏",
    "😁",
    "🤔",
    "🤯",
    "😱",
    "🤬",
    "😢",
    "🎉",
    "🤩",
    "🤮",
    "💩",
    "🙏",
    "👌",
    "🕊",
    "🤡",
    "🥱",
    "🥴",
    "😍",
    "🐳",
    "❤‍🔥",
    "🌚",
    "🌭",
    "💯",
    "🤣",
    "⚡",
    "🍌",
    "🏆",
    "💔",
    "🤨",
    "😐",
    "🍓",
    "🍾",
    "💋",
    "🖕",
    "😈",
    "😴",
    "😭",
    "🤓",
    "👻",
    "👨‍💻",
    "👀",
    "🎃",
    "🙈",
    "😇",
    "😨",
    "🤝",
    "✍",
    "🤗",
    "🫡",
    "🎅",
    "🎄",
    "☃",
    "💅",
    "🤪",
    "🗿",
    "🆒",
    "💘",
    "🙉",
    "🦄",
    "😘",
    "💊",
    "🙊",
    "😎",
    "👾",
    "🤷‍♂",
    "🤷",
    "🤷‍♀",
    "😡",
    "😂",
)

_TABLE: dict[str, dict] | None = None


def _plain(value: str) -> str:
    return (value or "").replace("\ufe0f", "")


def _emoji_char(char: str) -> bool:
    code = ord(char)
    return (
        0x1F300 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x27BF
        or 0x1F1E6 <= code <= 0x1F1FF
        or 0x1F3FB <= code <= 0x1F3FF
        or code in {0xFE0F, 0x200D, 0x20E3, 0x2764}
    )


def reaction_table() -> dict[str, dict]:
    global _TABLE
    if _TABLE is not None:
        return _TABLE
    catalog = json.loads((repo_root() / "shared" / "emoji-catalog.json").read_text(encoding="utf-8"))
    allowed = {_plain(symbol) for symbol in ALLOWED_REACTIONS}
    table: dict[str, dict] = {}
    for item in catalog.get("items") or []:
        if item.get("set_name") != "RestrictedEmoji":
            continue
        key = _plain(item.get("fallback") or "")
        if key in allowed and key not in table and str(item.get("custom_emoji_id") or "").isdigit():
            table[key] = item
    _TABLE = table
    return table


def _needles() -> list[tuple[str, dict]]:
    pairs: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for key, item in reaction_table().items():
        for form in (item.get("fallback") or "", key):
            if form and form not in seen:
                seen.add(form)
                pairs.append((form, item))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return pairs


def split_comment(text: str) -> tuple[list[dict], bool]:
    """Куски комментария. Второй флаг — в тексте был эмодзи вне списка реакций."""
    needles = _needles()
    parts: list[dict] = []
    buffer: list[str] = []
    foreign = False

    def flush() -> None:
        if buffer:
            parts.append({"text": "".join(buffer)})
            buffer.clear()

    index = 0
    while index < len(text):
        hit = None
        for form, item in needles:
            if text.startswith(form, index):
                hit = (form, item)
                break
        if hit:
            flush()
            form, item = hit
            parts.append(
                {
                    "text": item.get("fallback") or form,
                    "custom_emoji_id": str(item["custom_emoji_id"]),
                    "set_name": "RestrictedEmoji",
                }
            )
            index += len(form)
            if index < len(text) and text[index] == "\ufe0f":
                index += 1
            continue
        char = text[index]
        if _emoji_char(char):
            foreign = True
            index += 1
            continue
        buffer.append(char)
        index += 1
    flush()
    return parts, foreign


def clean_comment(text: str) -> str:
    parts, _foreign = split_comment(text or "")
    cleaned = "".join(part["text"] for part in parts)
    cleaned = "\n".join(line.strip() for line in cleaned.splitlines())
    return " ".join(cleaned.split()) if "\n" not in cleaned else cleaned.strip()


def has_foreign_emoji(text: str) -> bool:
    _parts, foreign = split_comment(text or "")
    return foreign
