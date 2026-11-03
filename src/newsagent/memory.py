from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")
STALE_LOCK = timedelta(minutes=90)
MEMORY_DAYS = 2


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "yclid", "gclid"}
    ]
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunsplit((parts.scheme.lower() or "https", host, parts.path.rstrip("/"), urlencode(query), ""))


def title_norm(text: str) -> str:
    cleaned = text.lower().replace("ё", "е")
    cleaned = re.sub(r"[^0-9a-zа-я]+", " ", cleaned)
    return " ".join(cleaned.split())


def similar(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def jaccard(left: str, right: str) -> float:
    a = set(left.split())
    b = set(right.split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


_LATIN_CONS = {
    "b": "б",
    "c": "к",
    "d": "д",
    "f": "ф",
    "g": "г",
    "h": "х",
    "j": "ж",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "v": "в",
    "w": "в",
    "x": "кс",
    "z": "з",
}
_CYR_VOWELS = set("аеёиоуыэюяйьъ")
_NAME = re.compile(r"[A-Za-zА-ЯЁ][A-Za-zА-ЯЁа-яё]{3,}")
_GENERIC_NAMES = {
    "breaking",
    "exclusive",
    "live",
    "news",
    "official",
    "report",
    "reports",
    "rumour",
    "rumors",
    "rumours",
    "transfer",
    "transfers",
    "update",
    "video",
    "watch",
    "видео",
    "новости",
    "новость",
    "обзор",
    "официально",
    "срочно",
    "трансфер",
    "трансферы",
    "эксклюзив",
}
_CLUB_SKELETONS: set[str] | None = None


def consonant_skeleton(token: str) -> str:
    chars: list[str] = []
    for char in token.lower().replace("ё", "е"):
        if "a" <= char <= "z":
            mapped = _LATIN_CONS.get(char)
            if mapped:
                chars.append(mapped)
        elif ("а" <= char <= "я" or char == "ё") and char not in _CYR_VOWELS:
            chars.append(char)
    return "".join(chars)


def _club_skeletons() -> set[str]:
    global _CLUB_SKELETONS
    if _CLUB_SKELETONS is None:
        from newsagent.lexicon import load_lexicon

        found: set[str] = set()
        for club in load_lexicon().get("clubs") or []:
            for alias in club.get("aliases") or []:
                plain = alias.replace("*", "")
                for part in re.findall(r"[a-zа-яе]{4,}", plain.lower().replace("ё", "е")):
                    skeleton = consonant_skeleton(part)
                    if len(skeleton) >= 2:
                        found.add(skeleton)
        _CLUB_SKELETONS = found
    return _CLUB_SKELETONS


def _skeleton_close(left: str, right: str) -> bool:
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    if len(short) < 4:
        return len(short) == 2 and short == long
    return long.startswith(short) and len(long) - len(short) <= 2


def _is_club_skeleton(skeleton: str, blocked: set[str]) -> bool:
    return any(_skeleton_close(skeleton, club) for club in blocked)


_SLUG_GLUE = {
    "after",
    "against",
    "before",
    "between",
    "board",
    "contender",
    "contenders",
    "culture",
    "daily",
    "despite",
    "during",
    "email",
    "entitlement",
    "football",
    "from",
    "goal",
    "hot",
    "inside",
    "into",
    "line",
    "manager",
    "meeting",
    "minutes",
    "news",
    "next",
    "over",
    "players",
    "preview",
    "report",
    "review",
    "seat",
    "shortlist",
    "story",
    "their",
    "this",
    "thrashing",
    "under",
    "with",
    "about",
    "betrayal",
    "champions",
    "league",
    "match",
    "nacelen",
    "podpisat",
    "podpishet",
    "press",
    "symptom",
    "toxic",
    "travmirovannogo",
    "travmirovannomu",
    "vingera",
    "zamenu",
}


def slug_person_skeletons(url: str) -> set[str]:
    """Фамилия из пары имя-фамилия в последнем куске URL, даже если заголовок её не содержит."""
    slug = urlsplit(url or "").path.lower().replace("ё", "е").rstrip("/").split("/")[-1]
    raw = [token for token in re.split(r"[-_]+", slug) if re.fullmatch(r"[a-z]{4,}", token)]
    blocked = _club_skeletons()
    kept: dict[int, str] = {}
    for index, token in enumerate(raw):
        if token in _GENERIC_NAMES or token in _SLUG_GLUE:
            continue
        skeleton = consonant_skeleton(token)
        if len(skeleton) < 4 or _is_club_skeleton(skeleton, blocked):
            continue
        kept[index] = skeleton
    return {skeleton for index, skeleton in kept.items() if index - 1 in kept}


def _story_names(title: str, url: str) -> set[str]:
    return person_skeletons(title) | slug_person_skeletons(url)


def person_skeletons(title: str) -> set[str]:
    blocked = _club_skeletons()
    found: set[str] = set()
    for token in _NAME.findall(title or ""):
        if token.lower().replace("ё", "е") in _GENERIC_NAMES:
            continue
        skeleton = consonant_skeleton(token)
        short_surname = len(skeleton) == 2 and token[:1].isupper()
        if not (len(skeleton) >= 4 or short_surname):
            continue
        if _is_club_skeleton(skeleton, blocked):
            continue
        found.add(skeleton)
    return found


def _same_person(left: set[str], right: set[str]) -> bool:
    for name in left:
        for previous in right:
            if _skeleton_close(name, previous):
                return True
    return False


def _day_clubs(event_key: str) -> tuple[str, set[str]]:
    parts = (event_key or "").split("|")
    if len(parts) < 3 or not parts[0]:
        return "", set()
    return parts[0], {club for club in parts[2].split(",") if club}


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE,
            title TEXT,
            title_norm TEXT,
            event_key TEXT,
            action TEXT,
            source_id TEXT,
            published_at TEXT,
            created_at TEXT,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS slots (
            publish_at TEXT PRIMARY KEY,
            run_id TEXT,
            status TEXT,
            message_id TEXT,
            updated_at TEXT
        );
        """
    )
    return conn


def _now() -> str:
    return datetime.now(MSK).isoformat(timespec="seconds")


def list_scheduled(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT publish_at, message_id, run_id FROM slots WHERE status = 'scheduled'"
    ).fetchall()
    return [
        {"publish_at": row["publish_at"], "message_id": row["message_id"] or "", "run_id": row["run_id"] or ""}
        for row in rows
    ]


def occupied_slots(conn: sqlite3.Connection) -> set[datetime]:
    rows = conn.execute(
        "SELECT publish_at, status, updated_at FROM slots WHERE status IN ('preparing', 'scheduled', 'sent')"
    ).fetchall()
    taken: set[datetime] = set()
    now = datetime.now(MSK)
    for row in rows:
        updated = datetime.fromisoformat(row["updated_at"])
        if row["status"] == "preparing" and now - updated > STALE_LOCK:
            continue
        taken.add(datetime.fromisoformat(row["publish_at"]))
    return taken


def try_lock_slot(conn: sqlite3.Connection, publish_at: datetime, run_id: str) -> bool:
    key = publish_at.astimezone(MSK).replace(microsecond=0).isoformat(timespec="seconds")
    now = _now()
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute("SELECT status, updated_at, run_id FROM slots WHERE publish_at = ?", (key,)).fetchone()
    if row and row["status"] in {"preparing", "scheduled", "sent"}:
        updated = datetime.fromisoformat(row["updated_at"])
        stale = row["status"] == "preparing" and datetime.now(MSK) - updated > STALE_LOCK
        same_run = row["run_id"] == run_id and row["status"] == "preparing"
        if not stale and not same_run:
            conn.execute("COMMIT")
            return False
    conn.execute(
        """
        INSERT INTO slots (publish_at, run_id, status, message_id, updated_at)
        VALUES (?, ?, 'preparing', '', ?)
        ON CONFLICT(publish_at) DO UPDATE SET
            run_id = excluded.run_id,
            status = 'preparing',
            updated_at = excluded.updated_at
        """,
        (key, run_id, now),
    )
    conn.execute("COMMIT")
    return True


def set_slot_status(
    conn: sqlite3.Connection,
    publish_at: datetime,
    status: str,
    run_id: str,
    message_id: str = "",
) -> None:
    key = publish_at.astimezone(MSK).replace(microsecond=0).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO slots (publish_at, run_id, status, message_id, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(publish_at) DO UPDATE SET
            run_id = excluded.run_id,
            status = excluded.status,
            message_id = excluded.message_id,
            updated_at = excluded.updated_at
        """,
        (key, run_id, status, message_id, _now()),
    )
    conn.commit()


def prune_history(conn: sqlite3.Connection, now: datetime | None = None) -> int:
    """Оставляет истории постов и слоты только за последние два дня."""
    moment = now or datetime.now(MSK)
    cutoff = (moment - timedelta(days=MEMORY_DAYS)).isoformat(timespec="seconds")
    stories = conn.execute("DELETE FROM stories WHERE created_at < ?", (cutoff,)).rowcount
    conn.execute("DELETE FROM slots WHERE publish_at < ?", (cutoff,))
    conn.commit()
    return stories


def is_duplicate(conn: sqlite3.Connection, item: dict) -> tuple[bool, str]:
    prune_history(conn)
    url = canonical_url(item["url"])
    row = conn.execute("SELECT id FROM stories WHERE url = ?", (url,)).fetchone()
    if row:
        return True, "url"
    norm = title_norm(item.get("title") or "")
    since = (datetime.now(MSK) - timedelta(days=MEMORY_DAYS)).isoformat(timespec="seconds")
    recent = conn.execute(
        """
        SELECT url, title, title_norm, event_key, action FROM stories
        WHERE created_at >= ? AND status IN ('scheduled', 'sent', 'reserved')
        """,
        (since,),
    ).fetchall()
    clubs = item.get("clubs") or []
    day, event_clubs = _day_clubs(item.get("event_key") or "")
    names = _story_names(item.get("title") or "", item.get("url") or "") if day and event_clubs else set()
    for previous in recent:
        if similar(norm, previous["title_norm"] or "") >= 0.84:
            return True, "title"
        if item.get("event_key") and item["event_key"] == previous["event_key"]:
            if previous["action"] == "result" and len(clubs) >= 2:
                return True, "match"
            if jaccard(norm, previous["title_norm"] or "") >= 0.4:
                return True, "event"
        if not names:
            continue
        prev_day, prev_clubs = _day_clubs(previous["event_key"] or "")
        if (event_clubs & prev_clubs) and _same_person(
            names, _story_names(previous["title"] or "", previous["url"] or "")
        ):
            return True, "player"
    return False, ""


def remember_story(conn: sqlite3.Connection, item: dict, status: str) -> None:
    url = canonical_url(item["url"])
    title = item.get("title") or ""
    conn.execute(
        """
        INSERT INTO stories (url, title, title_norm, event_key, action, source_id, published_at, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            title_norm = excluded.title_norm,
            event_key = excluded.event_key,
            action = excluded.action,
            status = excluded.status,
            created_at = excluded.created_at
        """,
        (
            url,
            title,
            title_norm(title),
            item.get("event_key") or "",
            item.get("action") or "",
            item.get("source_id") or "",
            item.get("published_at") or "",
            _now(),
            status,
        ),
    )
    conn.commit()


def reserve_story(conn: sqlite3.Connection, item: dict) -> bool:
    """Атомарно резервирует URL перед внешней отправкой."""
    url = canonical_url(item["url"])
    title = item.get("title") or ""
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO stories
            (url, title, title_norm, event_key, action, source_id, published_at, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'reserved')
        """,
        (
            url,
            title,
            title_norm(title),
            item.get("event_key") or "",
            item.get("action") or "",
            item.get("source_id") or "",
            item.get("published_at") or "",
            _now(),
        ),
    )
    conn.commit()
    return cursor.rowcount == 1


def release_story_reservation(conn: sqlite3.Connection, item: dict) -> None:
    conn.execute(
        "DELETE FROM stories WHERE url = ? AND status = 'reserved'",
        (canonical_url(item["url"]),),
    )
    conn.commit()


def url_hash(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()[:16]
