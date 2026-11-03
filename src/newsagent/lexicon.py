from __future__ import annotations

import json
import re
from pathlib import Path

from newsagent.runtime import repo_root

ACTION_RULES: list[tuple[str, list[str]]] = [
    ("transfer", ["transfer", "signing", "signs", "sign ", "deal", "трансфер", "переход", "подписал", "подпишет", "аренда", "купил", "купит"]),
    ("injury", ["injur", "травм", "поврежд", "выбыл", "limps off"]),
    ("sack", ["sack", "fired", "dismiss", "увол", "отставк"]),
    ("red-card", ["red card", "sent off", "красную карточ", "удален", "удалён"]),
    ("contract", ["contract", "контракт", "продлил", "продлит"]),
    ("debut", ["debut", "дебют"]),
    ("lineup", ["line-up", "lineup", "starting xi", "состав на матч"]),
    ("result", []),
]

SCORE_RE = re.compile(r"\d+\s*[:\-–]\s*\d+")
TIP_RE = re.compile(r"прогноз|ставк|коэффициент|букмекер|экспресс", re.IGNORECASE)
_MOTOR = re.compile(
    r"(?<!\w)(?:formula(?:[\s-]*(?:1|one))|f1|формула(?:[\s-]*1)?)(?!\w)|/auto(?:/|$)|formulaone|formula-1",
    re.IGNORECASE,
)
_DIGEST = re.compile(r"football[\s-]+daily|email[\s-]+digest|видео[\s-]?дайджест|video[\s-]+digest", re.IGNORECASE)


def load_lexicon(path: Path | None = None) -> dict:
    file_path = path or (repo_root() / "shared" / "football_lexicon.json")
    return json.loads(file_path.read_text(encoding="utf-8"))


def _pattern(alias: str) -> re.Pattern[str]:
    stem = alias.lower().replace("ё", "е")
    if stem.endswith("*"):
        return re.compile(rf"(?<!\w){re.escape(stem[:-1])}", re.IGNORECASE)
    return re.compile(rf"(?<!\w){re.escape(stem)}(?!\w)", re.IGNORECASE)


def find_ids(text: str, entries: list[dict]) -> list[str]:
    lowered = text.lower().replace("ё", "е")
    found: list[str] = []
    ordered = sorted(entries, key=lambda item: max(len(alias) for alias in item["aliases"]), reverse=True)
    for entry in ordered:
        if entry["id"] in found:
            continue
        for alias in sorted(entry["aliases"], key=len, reverse=True):
            if _pattern(alias.replace("ё", "е")).search(lowered):
                found.append(entry["id"])
                break
    return found


def merge_story_clubs(clubs: list[str], *texts: str, lexicon: dict | None = None) -> list[str]:
    """Дополняет clubs из русского/английского текста поста и карточки (до двух клубов)."""
    entries = (lexicon or load_lexicon())["clubs"]
    merged: list[str] = []
    for club in clubs:
        if club not in merged:
            merged.append(club)
    for text in texts:
        if not (text or "").strip():
            continue
        found = find_ids(text, entries)
        if len(found) >= 2:
            return found[:2]
        for club in found:
            if club not in merged:
                merged.append(club)
    return merged


def detect_action(text: str) -> str:
    lowered = text.lower().replace("ё", "е")
    if SCORE_RE.search(lowered):
        return "result"
    for action, needles in ACTION_RULES:
        if action == "result":
            continue
        if any(needle in lowered for needle in needles):
            return action
    return "news"


def classify(title: str, summary: str, lexicon: dict | None = None, url: str = "") -> dict:
    lexicon = lexicon or load_lexicon()
    text = f"{title}\n{summary}".replace("ё", "е")
    lowered = text.lower()
    clubs = find_ids(text, lexicon["clubs"])
    competitions = find_ids(text, lexicon["competitions"])
    domestic = find_ids(text, [{"id": item, "aliases": [item]} for item in lexicon["domestic_ru"]])
    domestic += [stem for stem in lexicon.get("domestic_stems", []) if re.search(rf"(?<!\w){re.escape(stem)}", lowered)]
    other_sport = any(_pattern(word).search(lowered) for word in lexicon["other_sports"])
    football_word = any(_pattern(word).search(lowered) for word in lexicon["football_words"])
    action = detect_action(text)
    club_entries = {item["id"]: item for item in lexicon["clubs"]}
    top = any(club_entries[club].get("tier") == "top" for club in clubs)
    foreign = bool(clubs or competitions)
    located = f"{title}\n{summary}\n{url}"

    drop_reason = ""
    if _DIGEST.search(located):
        drop_reason = "digest"
    elif _MOTOR.search(located):
        drop_reason = "other_sport"
    elif TIP_RE.search(lowered):
        drop_reason = "betting"
    elif other_sport and not foreign:
        drop_reason = "other_sport"
    elif domestic and not foreign:
        drop_reason = "domestic_ru"
    elif not foreign and not football_word:
        drop_reason = "not_football"

    tier = 6 if top or any(item in competitions for item in ("ucl", "world-cup", "euros")) else (3 if foreign else 0)
    return {
        "keep": not drop_reason,
        "drop_reason": drop_reason,
        "clubs": clubs,
        "competitions": competitions,
        "action": action,
        "tier": tier,
        "domestic": domestic,
    }


def event_key(day: str, action: str, clubs: list[str]) -> str:
    if not clubs:
        return ""
    return f"{day}|{action}|{','.join(sorted(clubs))}"
