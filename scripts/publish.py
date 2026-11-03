#!/usr/bin/env python3
from __future__ import annotations

import mimetypes
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.memory import (  # noqa: E402
    connect,
    release_story_reservation,
    remember_story,
    reserve_story,
    set_slot_status,
)
from newsagent.runtime import iso, load_dotenv, now_msk, parse_iso, read_json, repo_root, write_json  # noqa: E402
from newsagent.schedule import SCHEDULE_BUFFER, delivery_mode  # noqa: E402

MSK = __import__("zoneinfo").ZoneInfo("Europe/Moscow")

PUBLISH_ATTEMPTS = 3
PUBLISH_RETRY_DELAY_SEC = 2


def run_dir_from(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def mime_of(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Telegram HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.RequestError):
        return f"Telegram request failed: {exc.__class__.__name__}"
    text = str(exc)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        text = text.replace(token, "[redacted]")
    return text[:500]


def transient_publish_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429} or exc.response.status_code >= 500
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    lowered = str(exc).lower()
    return any(
        needle in lowered
        for needle in (
            "server closed the connection",
            "connection reset",
            "connection aborted",
            "incompleteread",
        )
    )


def send_with_retries(send):
    last: Exception | None = None
    for attempt in range(PUBLISH_ATTEMPTS):
        try:
            return send()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt >= PUBLISH_ATTEMPTS - 1 or not transient_publish_error(exc):
                raise
            time.sleep(PUBLISH_RETRY_DELAY_SEC * (attempt + 1))
    raise last or RuntimeError("publish failed")


def resolve_mode(plan: dict, publish_at, reason: str, ad_times: list, now) -> str:
    mode = delivery_mode(now, publish_at, reason, ad_times)
    if plan.get("batch_defer") and publish_at > now:
        return "schedule"
    if publish_at > now + SCHEDULE_BUFFER and mode == "send":
        return "schedule"
    return mode


def send_bot(chat: str, photo: Path, caption: str, schedule_at: int | None) -> dict:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    data = {"chat_id": chat, "caption": caption, "parse_mode": "HTML"}
    params = {}
    if schedule_at:
        stamp = str(int(schedule_at))
        data["schedule_date"] = stamp
        params["schedule_date"] = stamp
    with photo.open("rb") as handle:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            params=params,
            data=data,
            files={"photo": (photo.name, handle, mime_of(photo))},
            timeout=60,
        )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description") or "sendPhoto failed")
    return payload["result"]


def send_user(chat: str, photo: Path, plain: str, entities: list[dict], schedule_at):
    from telethon.sessions import StringSession
    from telethon.sync import TelegramClient
    from telethon.tl.types import (
        MessageEntityBlockquote,
        MessageEntityBold,
        MessageEntityCustomEmoji,
        MessageEntityItalic,
    )

    mapping = {
        "bold": MessageEntityBold,
        "italic": MessageEntityItalic,
        "blockquote": MessageEntityBlockquote,
    }
    formatted = []
    for item in entities:
        if item["type"] == "custom_emoji":
            formatted.append(MessageEntityCustomEmoji(item["offset"], item["length"], int(item["custom_emoji_id"])))
        else:
            formatted.append(mapping[item["type"]](item["offset"], item["length"]))
    client = TelegramClient(
        StringSession(os.environ["TELEGRAM_STRING_SESSION"]),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"],
        connection_retries=1,
        retry_delay=1,
        auto_reconnect=False,
        timeout=20,
    )
    client.connect()
    if not client.is_connected():
        raise ConnectionError("Telethon did not connect")
    try:
        kwargs = {"caption": plain, "formatting_entities": formatted}
        if schedule_at is not None:
            kwargs["schedule"] = schedule_at
        return client.send_file(chat, str(photo), **kwargs)
    finally:
        client.disconnect()


def slot_already_done(conn, publish_at, run_id: str) -> tuple[str, str] | None:
    key = publish_at.astimezone(MSK).replace(microsecond=0).isoformat(timespec="seconds")
    row = conn.execute(
        "SELECT status, message_id, run_id FROM slots WHERE publish_at = ?",
        (key,),
    ).fetchone()
    if not row or row["status"] not in {"scheduled", "sent"} or not row["message_id"]:
        return None
    if row["run_id"] == run_id:
        return row["status"], str(row["message_id"])
    return row["status"], str(row["message_id"])


def main() -> int:
    load_dotenv()
    if len(sys.argv) != 3 or sys.argv[1] != "--run-dir":
        print("usage: publish.py --run-dir <dir>")
        return 1
    run_dir = run_dir_from(sys.argv[2])
    result_path = run_dir / "publish-result.json"
    if result_path.exists():
        previous = read_json(result_path)
        if previous.get("status") in {"sent", "scheduled"} and previous.get("message_id"):
            print(f"already_published message_id={previous['message_id']}")
            return 0
    critic = read_json(run_dir / "critic.json")
    machine = read_json(run_dir / "machine.json")
    if critic.get("verdict") != "PASS" or machine.get("status") != "PASS":
        print("REFUSE publish before critic and machine PASS")
        return 1
    plan = read_json(run_dir / "slot-plan.json")
    ads = read_json(run_dir / "ads.json")
    caption = read_json(run_dir / "caption.json")
    photo = read_json(run_dir / "photo.json")
    design_path = run_dir / "design.json"
    review_path = run_dir / "photo-review.json"
    if not design_path.exists() or not review_path.exists():
        print("REFUSE publish without design and photo review")
        return 1
    design = read_json(design_path)
    review = read_json(review_path)
    if design.get("status") != "ok" or not design.get("file") or review.get("verdict") != "PASS":
        print("REFUSE publish before design and photo review PASS")
        return 1
    photo = {**photo, "file": design["file"]}
    story = read_json(run_dir / "story.json")
    context = read_json(run_dir / "context.json")
    publish_at = parse_iso(plan["publish_at"])
    ad_times = ads.get("items") or [parse_iso(item) for item in ads.get("slots") or []]
    now = now_msk()
    mode = resolve_mode(plan, publish_at, plan["reason"], ad_times, now)
    if mode == "wait_then_send":
        delay = (publish_at - now).total_seconds()
        if 0 < delay <= 25:
            time.sleep(delay)
        now = now_msk()
        mode = resolve_mode(plan, publish_at, plan["reason"], ad_times, now)
        if mode == "wait_then_send":
            mode = "abort_too_early"
    if mode.startswith("abort"):
        conn = connect(repo_root() / "memory" / "news.db")
        set_slot_status(conn, publish_at, "failed", context["run_id"])
        write_json(result_path, {"status": mode, "publish_at": iso(publish_at)})
        print(mode)
        return 1
    allow = os.environ.get("PUBLISH_ALLOW", "no").strip().lower() == "yes"
    result = {
        "status": "dry_run" if not allow else mode,
        "publish_at": iso(publish_at),
        "reason": plan["reason"],
        "mode": mode,
    }
    conn = connect(repo_root() / "memory" / "news.db")
    existing = slot_already_done(conn, publish_at, context["run_id"])
    if existing:
        status, message_id = existing
        result.update({"status": status, "message_id": message_id, "detail": "slot_already_occupied"})
        write_json(result_path, result)
        print(f"already_published message_id={message_id}")
        return 0
    if not allow:
        set_slot_status(conn, publish_at, "skipped", context["run_id"])
        write_json(result_path, result)
        print("dry_run")
        return 0
    schedule_at = publish_at if mode == "schedule" else None
    if schedule_at and schedule_at <= now:
        print("REFUSE schedule time is in the past")
        return 1
    backend = os.environ.get("PUBLISH_BACKEND", "user").strip() or "user"
    photo_path = run_dir / photo["file"]
    if not photo_path.exists():
        print("REFUSE designed image is missing")
        return 1
    if not reserve_story(conn, story):
        result.update({"status": "duplicate", "detail": "story URL is already reserved or published"})
        write_json(result_path, result)
        print("REFUSE duplicate story")
        return 1
    schedule_dt = schedule_at
    chat = os.environ["NEWS_CHANNEL_ID"]
    sent = None
    message_id = ""
    used_backend = backend
    errors: list[str] = []
    if backend == "user":
        try:
            sent = send_with_retries(
                lambda: send_user(chat, photo_path, caption["plain"], caption["entities"], schedule_dt)
            )
            message_id = str(getattr(sent, "id", ""))
        except Exception as exc:  # noqa: BLE001
            errors.append(safe_error(exc))
            used_backend = "bot"
    if not message_id:
        schedule_stamp = int(schedule_at.timestamp()) if schedule_at else None
        try:
            sent = send_with_retries(
                lambda: send_bot(chat, photo_path, caption["html"], schedule_stamp)
            )
            message_id = str(sent.get("message_id", ""))
        except Exception as exc:  # noqa: BLE001
            release_story_reservation(conn, story)
            set_slot_status(conn, publish_at, "failed", context["run_id"])
            result["status"] = "error"
            result["detail"] = "; ".join(errors + [safe_error(exc)]).strip("; ")
            write_json(result_path, result)
            print(f"ERROR {result['detail']}")
            return 1
    status = "scheduled" if mode == "schedule" else "sent"
    result.update(
        {
            "status": status,
            "message_id": message_id,
            "backend": used_backend,
            "detail": errors[0] if errors else "",
        }
    )
    write_json(result_path, result)
    set_slot_status(conn, publish_at, status, context["run_id"], message_id)
    remember_story(conn, story, status)
    print(f"{status} message_id={message_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
