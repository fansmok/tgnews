#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.emoji_sync import catalog_path, sync_catalog, token_from_env  # noqa: E402
from newsagent.runtime import load_dotenv, read_json, repo_root, write_json  # noqa: E402


def main() -> int:
    load_dotenv()
    config = read_json(repo_root() / "shared" / "emoji-catalog.json")
    packs = config.get("packs") or []
    try:
        token = token_from_env()
    except RuntimeError as exc:
        print(f"ERROR {exc}")
        return 1
    synced = sync_catalog(token, packs)
    write_json(catalog_path(), {"packs": packs, "items": synced["items"]})
    print(f"items={len(synced['items'])} errors={len(synced['errors'])}")
    for error in synced["errors"]:
        print(f"WARN {error}")
    return 0 if synced["items"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
