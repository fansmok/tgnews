#!/usr/bin/env python3
"""Переносит уже собранный отложенный пост на другую минуту. Текст и карточка те же."""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.channels import delete_scheduled  # noqa: E402
from newsagent.memory import connect, set_slot_status  # noqa: E402
from newsagent.runtime import iso, load_dotenv, parse_iso, read_json, repo_root, write_json  # noqa: E402


def _publish():
    spec = importlib.util.spec_from_file_location("tg_publish", ROOT / "scripts" / "publish.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--from", dest="old", required=True)
    parser.add_argument("--to", required=True)
    parser.add_argument("--message-id", default="")
    args = parser.parse_args()
    root = repo_root()
    run_dir = root / "memory" / "runs" / args.run_id
    design_path = run_dir / "design.json"
    caption_path = run_dir / "caption.json"
    if not design_path.exists() or not caption_path.exists():
        print("ERROR post files are missing")
        return 1
    design = read_json(design_path)
    caption = read_json(caption_path)
    photo = run_dir / (design.get("file") or "")
    if not photo.exists():
        print("ERROR designed image is missing")
        return 1
    new_at = parse_iso(args.to)
    old_at = parse_iso(args.old)
    chat = os.environ.get("NEWS_CHANNEL_ID", "").strip()
    backend = os.environ.get("PUBLISH_BACKEND", "bot").strip() or "bot"
    publisher = _publish()
    try:
        if backend == "user":
            sent = publisher.send_user(chat, photo, caption["plain"], caption["entities"], new_at)
            message_id = str(getattr(sent, "id", ""))
        else:
            sent = publisher.send_bot(chat, photo, caption["html"], int(new_at.timestamp()))
            message_id = str(sent.get("message_id", ""))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {publisher.safe_error(exc)}")
        return 1
    if args.message_id:
        delete_scheduled(chat, args.message_id)
    conn = connect(root / "memory" / "news.db")
    set_slot_status(conn, old_at, "skipped", args.run_id, "")
    set_slot_status(conn, new_at, "scheduled", args.run_id, message_id)
    result_path = run_dir / "publish-result.json"
    if result_path.exists():
        result = read_json(result_path)
        result.update({"status": "scheduled", "publish_at": iso(new_at), "message_id": message_id, "moved_from": iso(old_at)})
        write_json(result_path, result)
    print(f"moved {iso(old_at)} -> {iso(new_at)} message_id={message_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
