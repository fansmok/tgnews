#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.runtime import clock_status, load_dotenv, now_msk, repo_root  # noqa: E402
from newsagent.mtproto import is_cursor_cloud, probe_mtproto, publish_needs_mtproto  # noqa: E402

REQUIRED_DIRS = [
    "agents",
    "skills",
    ".cursor/agents",
    ".cursor/skills",
    "shared",
    "scripts",
    "src/newsagent",
    "memory",
    "memory/runs",
]
ENV_REQUIRED = ["TELEGRAM_BOT_TOKEN", "NEWS_CHANNEL_ID", "ADS_CHANNEL"]
ENV_OPTIONAL = [
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_STRING_SESSION",
    "PUBLISH_ALLOW",
    "PUBLISH_BACKEND",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "KIE_API_KEY",
    "KIE_MODEL",
]


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return ""
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file_path.relative_to(path).as_posix().encode())
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    load_dotenv()
    root = repo_root()
    errors = 0
    warnings = 0

    if sys.version_info < (3, 9):
        print("ERROR python >= 3.9 required")
        errors += 1
    else:
        print(f"OK python {sys.version.split()[0]}")

    for name in ("httpx", "feedparser", "bs4", "PIL"):
        try:
            importlib.import_module(name)
            print(f"OK dependency {name}")
        except ImportError:
            print(f"ERROR dependency {name} missing")
            errors += 1

    for relative in REQUIRED_DIRS:
        if (root / relative).exists():
            print(f"OK dir {relative}")
        else:
            print(f"ERROR dir {relative} missing")
            errors += 1

    for left, right in (("agents", ".cursor/agents"), ("skills", ".cursor/skills")):
        if tree_hash(root / left) == tree_hash(root / right) and tree_hash(root / left):
            print(f"OK sync {left}")
        else:
            print(f"ERROR sync {left} != {right}; run python3 scripts/sync_cursor_tree.py")
            errors += 1

    probe = root / "memory" / ".write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print("OK memory writable")
    except OSError:
        print("ERROR memory is not writable")
        errors += 1

    env_path = root / ".env"
    if env_path.exists():
        mode = env_path.stat().st_mode & 0o777
        if mode & 0o077:
            print(f"WARN .env permissions are {mode:o}; expected 600")
            warnings += 1
        else:
            print("OK .env permissions 600")

    try:
        from zoneinfo import ZoneInfo

        ZoneInfo("Europe/Moscow")
        print("OK timezone Europe/Moscow")
    except Exception:  # noqa: BLE001
        print("ERROR timezone Europe/Moscow")
        errors += 1

    status = clock_status()
    moment = now_msk().isoformat(timespec="seconds")
    if status == "ok":
        print(f"OK clock Moscow {moment}")
    elif status == "corrected":
        print(f"OK clock corrected, Moscow {moment}")
    else:
        print(f"WARN clock unverified, system Moscow {moment}")
        warnings += 1

    for name in ENV_REQUIRED:
        if os.environ.get(name, "").strip():
            print(f"OK env {name} configured")
        else:
            print(f"WARN env {name} missing")
            warnings += 1
    for name in ENV_OPTIONAL:
        state = "configured" if os.environ.get(name, "").strip() else "missing"
        print(f"OK env {name} {state}")

    if publish_needs_mtproto():
        ok, detail = probe_mtproto()
        if ok:
            print("OK mtproto Telethon connect")
        elif is_cursor_cloud():
            print(f"ERROR mtproto {detail}")
            errors += 1
        else:
            print(f"WARN mtproto {detail}")
            warnings += 1

    catalog = root / "shared" / "emoji-catalog.json"
    try:
        import json

        items = json.loads(catalog.read_text(encoding="utf-8")).get("items") or []
        if items:
            print(f"OK emoji catalog items={len(items)}")
        else:
            print("WARN emoji catalog is empty; run python3 scripts/sync_emoji.py")
            warnings += 1
    except (OSError, ValueError):
        print("ERROR emoji catalog is not valid json")
        errors += 1

    print(f"SUMMARY errors={errors} warnings={warnings}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
