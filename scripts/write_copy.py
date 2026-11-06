#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.copytext import (  # noqa: E402
    BOLD_SPAN_RULE,
    MENU_FACT_RULE,
    _unwrap_quote,
    clause_outside_title,
    detach_quote,
    keep_summary_fact,
    person_span,
    source_for_copy,
    strip_emoji,
)
from newsagent.gemini import GeminiUnavailable, generate_json  # noqa: E402
from newsagent.runtime import load_dotenv, read_json, write_json  # noqa: E402

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "paragraphs": {"type": "ARRAY", "items": {"type": "STRING"}},
        "bold_spans": {"type": "ARRAY", "items": {"type": "STRING"}},
        "quote_text": {"type": "STRING"},
        "quote_author": {"type": "STRING"},
    },
    "required": ["title", "paragraphs", "bold_spans", "quote_text", "quote_author"],
}


def article_text(url: str, cached_path: Path | None = None) -> str:
    if not url:
        return ""
    if cached_path and cached_path.exists():
        page = cached_path.read_text(encoding="utf-8", errors="replace")
    else:
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return ""
        page = response.text
    soup = BeautifulSoup(page, "lxml")
    for tag in soup.select("script, style, noscript"):
        tag.decompose()
    node = soup.select_one("article") or soup.select_one("main") or soup.body
    if node is None:
        return ""
    return node.get_text("\n", strip=True)[:6000]


TELEGRAM_RULE = (
    "Источник — пост чужого Telegram-канала. Сделай лёгкий рерайт: те же факты, цифры, имена и цитаты, "
    "но фразы свои, а не копия поста. Заголовок обычным регистром, без капса и восклицаний. "
    "Опрос, призыв проголосовать, подпись канала, реплики админа и emoji из поста не переносятся."
)
SITE_RULE = (
    "Близость к источнику важнее красоты. Английский текст переведи близко к фразам источника. "
    "Русский текст почти оставь: убери рекламу, ссылки и «читайте также», подгони под формат."
)


def from_telegram(story: dict) -> bool:
    return story.get("source_kind") == "telegram"


def prompt(story: dict, source: str, policy: str, *, page_is_menu: bool = False) -> str:
    menu_note = ""
    if page_is_menu:
        menu_note = (
            "Текст страницы похож на меню сайта и в источник не входит. "
            "Не добавляй факты вне заголовка и summary карточки.\n\n"
        )
    source_rule = TELEGRAM_RULE if from_telegram(story) else SITE_RULE
    return f"""Ты готовишь подпись футбольной новости для Telegram.
Язык ответа: русский.

{policy}

{MENU_FACT_RULE}

{menu_note}{source_rule} Не добавляй факты, которых нет в заголовке и summary карточки. Если новость — реакция на чьи-то слова, в текст должны войти сами эти слова. Цитата того, кто только отреагировал, их не заменяет. Слов в карточке нет — не выдумывай их. Если в источнике «выступил с заявлением», «опубликовал обращение», «высказался по поводу», в текст должна войти суть заявления: что требуют, в чём обвиняют, что предлагают. Сути в карточке нет — не выдумывай её. Не пиши комментарий болельщика и не ставь emoji.

Заголовок, абзац и цитата не повторяют друг друга. В заголовке нет текста цитаты и нет двоеточия с чужой речью. Абзац не пересказывает заголовок даже другими словами: в нём только новый факт, которого в заголовке нет. Заголовок не закрывает весь текст карточки: факт из summary, которого нет в заголовке, остаётся абзацем. Если такого факта нет, paragraphs оставь пустым массивом. Цитату при этом всё равно положи в quote_text. Если цитата уже звучит в заголовке или абзаце, quote_text оставь пустым.

Заголовок до 120 символов, без emoji и без HTML: значок ставит отдельная роль. Абзацев 0–3, каждый до 320 символов. {BOLD_SPAN_RULE} Если в карточке есть прямая цитата и её ещё нет в заголовке, положи её в quote_text без кавычек и автора в quote_author. Нет цитаты — обе строки пустые. Цитату не расширяй.

Источник:
{source}

Карточка:
title: {story.get("title") or ""}
summary: {story.get("summary") or ""}
url: {story.get("url") or ""}
"""


def normalize(data: dict, source: str, summary: str = "") -> dict:
    title = strip_emoji(str(data.get("title") or ""))
    paragraphs = [strip_emoji(str(part)) for part in data.get("paragraphs") or []]
    paragraphs = [part for part in paragraphs if part][:3]
    quote_text = _unwrap_quote(str(data.get("quote_text") or ""))
    title, paragraphs, quote_text = detach_quote(title, paragraphs, quote_text)
    paragraphs = keep_summary_fact(title, paragraphs, summary)
    body = "\n".join(paragraphs)
    spans = []
    for span in data.get("bold_spans") or []:
        text = str(span).strip()
        if text and text in body and text not in spans:
            spans.append(text)
    if not spans and body:
        match = re.search(r"\d+\s*[:\–\-]\s*\d+|\d+", body)
        if match and match.group(0) in body:
            spans.append(match.group(0))
    if not spans and body:
        extra = person_span(body) or clause_outside_title(title, body)
        if extra and extra not in spans:
            spans.append(extra)
    quote_author = str(data.get("quote_author") or "").strip()
    quote = {"text": quote_text, "author": quote_author} if quote_text else None
    return {
        "title": title,
        "paragraphs": paragraphs,
        "bold_spans": spans,
        "quote": quote,
        "source_text": source[:4000],
        "engine": "gemini",
    }


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    story = read_json(run_dir / "story.json")
    policy = (ROOT / "shared" / "editorial-policy.md").read_text(encoding="utf-8")
    page = "" if from_telegram(story) else article_text(str(story.get("url") or ""), run_dir / "source-page.html")
    source, page_is_menu = source_for_copy(
        str(story.get("title") or ""),
        str(story.get("summary") or ""),
        page,
    )
    request = prompt(story, source, policy, page_is_menu=page_is_menu)
    rework_path = run_dir / "rework.json"
    if rework_path.exists():
        issues = [str(item) for item in read_json(rework_path).get("issues") or [] if item]
        if issues:
            request += "\nКритик вернул прошлую версию. Исправь:\n" + "\n".join(f"- {item}" for item in issues) + "\n"
    try:
        data, model = generate_json(
            request,
            SCHEMA,
            temperature=0.2,
        )
    except GeminiUnavailable as exc:
        print(f"gemini_unavailable {exc}")
        return 3
    copy = normalize(data, source, summary=str(story.get("summary") or ""))
    copy["model"] = model
    if not copy["title"]:
        print("gemini_unavailable empty copy")
        return 3
    write_json(run_dir / "copy.json", copy)
    print(f"copy via {model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
