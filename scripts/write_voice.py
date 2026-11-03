#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.gemini import GeminiUnavailable, generate_json  # noqa: E402
from newsagent.reactions import ALLOWED_REACTIONS, clean_comment  # noqa: E402
from newsagent.runtime import load_dotenv, read_json, repo_root, write_json  # noqa: E402

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "comment": {"type": "STRING"},
        "reason": {"type": "STRING"},
    },
    "required": ["comment", "reason"],
}


REACTION_MEANING = """Смысл знака должен совпадать со смыслом строки рядом с ним:
- согласие, «да», «прав», поддержка: 👍 💯 👏 🤝 🔥 ⚡ 🏆
- несогласие, «нет», сомнение: 👎 🤔 🤨 🥱 🤷
- грусть, провал, «увязнут»: 😢 😭 💔
- шок, сенсация: 😱 🤯
- восторг, любовь к игроку: 😍 🤩 ❤ 🥰
- насмешка, ирония, абсурд: 🤣 😁 🤡 🗿
Смеющиеся 🤣 😁 🤡 — только если сама строка шутка или насмешка. Под «да, он прав» смех не ставить."""


def previous_post(run_dir: Path) -> dict | None:
    """Голос соседнего более раннего поста этого дня: ритм реакций и уже занятые знаки."""
    parts = run_dir.name.split("-")
    if len(parts) < 3 or not parts[1].isdigit():
        return None
    day, stamp = parts[1], parts[2][:4]
    earlier = []
    for other in run_dir.parent.glob(f"R-{day}-*"):
        bits = other.name.split("-")
        if other == run_dir or len(bits) < 3 or bits[2][:4] >= stamp:
            continue
        voice_path = other / "voice.json"
        machine_path = other / "machine.json"
        if not voice_path.exists() or not machine_path.exists():
            continue
        if read_json(machine_path).get("status") != "PASS":
            continue
        earlier.append((bits[2][:4], read_json(voice_path)))
    if not earlier:
        return None
    return max(earlier, key=lambda item: item[0])[1]


def used_symbols(comment: str | None) -> list[str]:
    return [symbol for symbol in ALLOWED_REACTIONS if symbol in (comment or "")]


def prompt(copy: dict, soul: str, avoid: list[str] | None = None) -> str:
    quote = copy.get("quote") or {}
    paragraphs = "\n".join(copy.get("paragraphs") or [])
    symbols = " ".join(ALLOWED_REACTIONS)
    avoid_line = f"В прошлом посте уже были {' '.join(avoid)} — возьми другие.\n" if avoid else ""
    return f"""Ты решаешь, нужна ли короткая реплика болельщика к уже написанной новости.
Саму новость не переписывай.

{soul}

По умолчанию реплика не нужна: comment пустой строкой, reason not_needed.
Пиши её, только если в новости есть настоящая развилка, о которой болельщики спорят: отставка, громкий трансфер, разгром, скандал, «кто прав». Нейтральная новость, анонс, мнение эксперта без спора, протокол — без реплики.
Если нужна, comment — готовый текст до 200 символов, reason — poll или cheer.
Не повторяй заголовок. Не добавляй рекламу, ссылки и @sportonkp.
Эмодзи в реплике — только из этого списка реакций, другие знаки нельзя: {symbols}
{REACTION_MEANING}
Две позиции — два разных знака. {avoid_line}Публикация сама заменит эти знаки на анимированные из пака RestrictedEmoji. В текст пиши обычный символ.

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
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir
    soul = (ROOT / "shared" / "voice.md").read_text(encoding="utf-8")
    if "STATUS: ready" not in soul:
        write_json(run_dir / "voice.json", {"comment": None, "reason": "voice_not_configured", "engine": "gemini"})
        print("voice skipped")
        return 0
    copy = read_json(run_dir / "copy.json")
    previous = previous_post(run_dir)
    if previous and previous.get("comment"):
        write_json(run_dir / "voice.json", {"comment": None, "reason": "rhythm_previous_had_comment", "engine": "rule"})
        print("voice skipped: previous post already had a comment")
        return 0
    try:
        data, model = generate_json(prompt(copy, soul, used_symbols((previous or {}).get("comment"))), SCHEMA, temperature=0.5)
    except GeminiUnavailable as exc:
        print(f"gemini_unavailable {exc}")
        return 3
    write_json(run_dir / "voice.json", normalize(data, model))
    print(f"voice via {model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
