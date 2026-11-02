from __future__ import annotations

import html
import re
from dataclasses import dataclass

from newsagent.reactions import split_comment

AD_PATTERNS = [
    r"\berid\b",
    r"промокод",
    r"1xbet",
    r"1хбет",
    r"winline",
    r"fonbet",
    r"фонбет",
    r"betboom",
    r"букмекер",
    r"партн[её]рск",
    r"реклам[аыуе]",
    r"подписывай",
    r"читай(?:те)? также",
    r"наш канал",
    r"ставки на спорт",
]
AD_RE = re.compile("|".join(AD_PATTERNS), re.IGNORECASE)


@dataclass
class Emoji:
    custom_emoji_id: str
    fallback: str
    tags: list[str]


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def strip_ads(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        if AD_RE.search(line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def contains_ad(text: str) -> bool:
    return bool(AD_RE.search(text))


def mostly_cyrillic(text: str) -> bool:
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    if len(letters) < 8:
        return False
    cyrillic = sum(1 for char in letters if re.match(r"[А-Яа-яЁё]", char))
    return cyrillic / len(letters) >= 0.5


def longest_common_run(source: str, rewritten: str) -> int:
    def tokens(text: str) -> list[str]:
        return re.findall(r"[0-9A-Za-zА-Яа-яЁё]{2,}", text.lower().replace("ё", "е"))

    left = tokens(source)
    right = tokens(rewritten)
    if not left or not right:
        return 0
    best = 0
    for i in range(len(left)):
        for j in range(len(right)):
            run = 0
            while i + run < len(left) and j + run < len(right) and left[i + run] == right[j + run]:
                run += 1
            best = max(best, run)
    return best


def bold_ranges(text: str, spans: list[str]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for span in spans:
        if not span:
            continue
        start = 0
        while True:
            index = text.find(span, start)
            if index < 0:
                break
            ranges.append((index, index + len(span)))
            start = index + len(span)
    ranges.sort()
    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _bold_fragments(text: str, spans: list[str]) -> str:
    if not text:
        return ""
    ranges = bold_ranges(text, spans)
    if not ranges:
        return html.escape(text)
    chunks: list[str] = []
    cursor = 0
    for start, end in ranges:
        chunks.append(html.escape(text[cursor:start]))
        chunks.append(f"<b>{html.escape(text[start:end])}</b>")
        cursor = end
    chunks.append(html.escape(text[cursor:]))
    return "".join(chunks)


def _quote_text(text: str) -> str:
    cleaned = text.strip().strip("«»\"“”")
    return f"«{cleaned}»"


def render_post(post: dict) -> dict:
    title = (post.get("title") or "").strip()
    paragraphs = [part.strip() for part in post.get("paragraphs") or [] if part and part.strip()]
    spans = [span for span in post.get("bold_spans") or [] if span]
    title_emoji = post.get("title_emoji") or None
    paragraph_emoji = post.get("paragraph_emoji") or []
    quote = post.get("quote") or None
    comment = (post.get("comment") or "").strip()

    html_parts: list[str] = []
    plain_parts: list[str] = []
    entities: list[dict] = []

    def add(text: str, kinds: list[dict] | None = None) -> None:
        if not text:
            return
        offset = utf16_len("".join(plain_parts))
        plain_parts.append(text)
        for kind in kinds or []:
            entities.append(
                {
                    "type": kind["type"],
                    "offset": offset,
                    "length": utf16_len(text),
                    **({"custom_emoji_id": kind["custom_emoji_id"]} if "custom_emoji_id" in kind else {}),
                }
            )

    def add_emoji(emoji: dict | None) -> None:
        if not emoji:
            return
        fallback = emoji.get("fallback") or "⚽"
        emoji_id = str(emoji.get("custom_emoji_id") or "")
        if not emoji_id:
            html_parts.append(f"{html.escape(fallback)} ")
            add(f"{fallback} ")
            return
        html_parts.append(f'<tg-emoji emoji-id="{html.escape(emoji_id, quote=True)}">{fallback}</tg-emoji> ')
        add(fallback, [{"type": "custom_emoji", "custom_emoji_id": emoji_id}])
        add(" ")

    if isinstance(title_emoji, list):
        for single in title_emoji:
            add_emoji(single)
    else:
        add_emoji(title_emoji)
    html_parts.append(f"<b>{html.escape(title)}</b>")
    add(title, [{"type": "bold"}])
    add("\n\n")
    html_parts.append("\n\n")

    for index, paragraph in enumerate(paragraphs):
        emoji = paragraph_emoji[index] if index < len(paragraph_emoji) else None
        if emoji:
            add_emoji(emoji)
        html_parts.append(_bold_fragments(paragraph, spans))
        cursor = 0
        for start, end in bold_ranges(paragraph, spans):
            add(paragraph[cursor:start])
            add(paragraph[start:end], [{"type": "bold"}])
            cursor = end
        add(paragraph[cursor:])
        if index != len(paragraphs) - 1:
            add("\n\n")
            html_parts.append("\n\n")

    if quote and quote.get("text"):
        body = _quote_text(quote["text"])
        author = (quote.get("author") or "").strip()
        block = body if not author else f"{body}\n— {author}"
        add("\n\n")
        html_parts.append("\n\n<blockquote>")
        html_parts.append(html.escape(block))
        html_parts.append("</blockquote>")
        add(block, [{"type": "blockquote"}])

    if comment:
        add("\n\n")
        html_parts.append("\n\n")
        parts, _foreign = split_comment(comment)
        italic = False
        for part in parts:
            emoji_id = str(part.get("custom_emoji_id") or "")
            if emoji_id:
                if italic:
                    html_parts.append("</i>")
                    italic = False
                fallback = part["text"]
                html_parts.append(f'<tg-emoji emoji-id="{html.escape(emoji_id, quote=True)}">{fallback}</tg-emoji>')
                add(fallback, [{"type": "custom_emoji", "custom_emoji_id": emoji_id}])
                continue
            if not italic:
                html_parts.append("<i>")
                italic = True
            html_parts.append(html.escape(part["text"]))
            add(part["text"], [{"type": "italic"}])
        if italic:
            html_parts.append("</i>")

    plain = "".join(plain_parts)
    caption_html = "".join(html_parts)
    visible = re.sub(r"<[^>]+>", "", caption_html)
    return {
        "html": caption_html,
        "plain": plain,
        "entities": entities,
        "visible_length": len(visible),
        "utf16_length": utf16_len(plain),
    }
