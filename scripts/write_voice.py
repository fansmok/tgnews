#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.gemini import GeminiUnavailable, generate_json  # noqa: E402
from newsagent.reactions import ALLOWED_REACTIONS, clean_comment  # noqa: E402
from newsagent.runtime import load_dotenv, read_json, write_json  # noqa: E402

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "comment": {"type": "STRING"},
        "reason": {"type": "STRING"},
    },
    "required": ["comment", "reason"],
}


def prompt(copy: dict, soul: str) -> str:
    quote = copy.get("quote") or {}
    paragraphs = "\n".join(copy.get("paragraphs") or [])
    symbols = " ".join(ALLOWED_REACTIONS)
    pairs = ("🏆🤔", "🔥🤨", "👏🤷", "🥰😐", "🤩💔", "🤣😭", "💯👎", "😱🤝", "😎🥱", "🎉🗿", "😁🤬", "😍😢")
    pair = pairs[zlib.crc32((copy.get("title") or "").encode()) % len(pairs)]
    return f"""Ты решаешь, нужна ли короткая реплика болельщика к уже написанной новости.
Саму новость не переписывай.

{soul}

Если реплика не нужна, comment оставь пустой строкой и reason поставь not_needed.
Если нужна, comment — готовый текст до 200 символов, reason — poll или cheer.
Не повторяй заголовок. Не добавляй рекламу, ссылки и @sportonkp.
Эмодзи в реплике — только из этого списка реакций, другие знаки нельзя: {symbols}
Бери разные знаки по смыслу, не одну и ту же пару в каждой новости. Для этого выпуска, если смыслу не противоречит, начни с {pair[0]} и {pair[1]}. Две позиции — два разных знака.
Публикация сама заменит эти знаки на анимированные из пака RestrictedEmoji. В текст пиши обычный символ.

Заголовок: {copy.get("title") or ""}
Текст:
{paragraphs}
Цитата: {quote.get("text") or ""}
Автор: {quote.get("author") or ""}
"""


def normalize(data: dict, model: str) -> dict:
    comment = str(data.get("comment") or "").strip()
    reason = str(data.get("reason") or "").strip() or "not_needed"
    if not comment:
        return {"comment": None, "reason": reason, "engine": "gemini", "model": model}
    comment = clean_comment(comment)
    if not comment:
        return {"comment": None, "reason": reason, "engine": "gemini", "model": model}
    if len(comment) > 220:
        comment = comment[:220].rstrip()
    return {"comment": comment, "reason": reason, "engine": "gemini", "model": model}


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    soul = (ROOT / "shared" / "voice.md").read_text(encoding="utf-8")
    if "STATUS: ready" not in soul:
        write_json(run_dir / "voice.json", {"comment": None, "reason": "voice_not_configured", "engine": "gemini"})
        print("voice skipped")
        return 0
    copy = read_json(run_dir / "copy.json")
    try:
        data, model = generate_json(prompt(copy, soul), SCHEMA, temperature=0.7)
    except GeminiUnavailable as exc:
        print(f"gemini_unavailable {exc}")
        return 3
    write_json(run_dir / "voice.json", normalize(data, model))
    print(f"voice via {model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
