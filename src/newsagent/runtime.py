from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")
_SKEW_LIMIT = timedelta(seconds=90)
_TIME_URLS = (
    "https://www.google.com/generate_204",
    "https://api.telegram.org",
)
_OFFSET: timedelta | None = None
_CLOCK_STATUS = "unverified"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_dotenv() -> None:
    path = repo_root() / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def measure_clock_offset() -> timedelta:
    """Разница между Date в ответе Google или Telegram и часами компьютера."""
    global _OFFSET, _CLOCK_STATUS
    import httpx

    for url in _TIME_URLS:
        try:
            response = httpx.get(url, timeout=8.0)
        except Exception:
            continue
        header = response.headers.get("date")
        if not header:
            continue
        remote = parsedate_to_datetime(header)
        if remote.tzinfo is None:
            remote = remote.replace(tzinfo=timezone.utc)
        delta = remote.astimezone(timezone.utc) - utc_now()
        if abs(delta.total_seconds()) < _SKEW_LIMIT.total_seconds():
            _OFFSET = timedelta(0)
            _CLOCK_STATUS = "ok"
        else:
            _OFFSET = delta
            _CLOCK_STATUS = "corrected"
        return _OFFSET
    _OFFSET = timedelta(0)
    _CLOCK_STATUS = "unverified"
    return _OFFSET


def clock_offset() -> timedelta:
    if _OFFSET is None:
        return measure_clock_offset()
    return _OFFSET


def clock_status() -> str:
    clock_offset()
    return _CLOCK_STATUS


def now_msk() -> datetime:
    return (utc_now() + clock_offset()).astimezone(MSK)


def dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(dumps(data))
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return dt.astimezone(MSK)


def iso(dt: datetime) -> str:
    return dt.astimezone(MSK).isoformat(timespec="seconds")


def append_incident(
    *,
    role: str,
    run_id: str,
    severity: str,
    category: str,
    what: str,
    recovered: str,
    fix: str,
    files: list[str],
    queue_path: Path | None = None,
) -> str:
    path = queue_path or (repo_root() / "memory" / "pipeline-fix-queue.md")
    stamp = now_msk().strftime("%Y%m%d-%H%M")
    slug = "-".join(part for part in (role, category) if part)[:40]
    inc_id = f"INC-{stamp}-{slug}"
    block = f"""
## {inc_id}
status: open
run_date: {now_msk().date().isoformat()}
role: {role}
run_id: {run_id}
severity: {severity}
category: {category}

### What went wrong
- {what}

### How the agent recovered this run
- {recovered}

### Durable fix needed before next run
- {fix}

### Suggested files to inspect/change
{chr(10).join(f"- `{item}`" for item in files) or "- none"}

### Secrets
- none recorded

### Fixer resolution
- pending
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# Pipeline fix queue\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(block)
    return inc_id
