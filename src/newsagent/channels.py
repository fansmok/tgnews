from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from newsagent.runtime import iso, parse_iso, read_json, repo_root, write_json


def username_of(channel: str) -> str | None:
    value = channel.strip()
    if value.startswith("https://t.me/"):
        value = value.removeprefix("https://t.me/").split("/")[0]
    if value.startswith("@"):
        value = value[1:]
    if value.startswith("-") or value.lstrip("-").isdigit():
        return None
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,}", value):
        return value
    return None


def parse_public_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    messages: list[dict] = []
    for node in soup.select(".tgme_widget_message_wrap"):
        text_node = node.select_one(".tgme_widget_message_text")
        time_node = node.select_one("time")
        if not text_node or not time_node or not time_node.get("datetime"):
            continue
        messages.append(
            {
                "text": text_node.get_text("\n", strip=True),
                "message_at": datetime.fromisoformat(time_node["datetime"]),
            }
        )
    messages.reverse()
    return messages


def inspect_public(username: str) -> tuple[list[dict], bool]:
    response = httpx.get(
        f"https://t.me/s/{username}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
        follow_redirects=True,
    )
    response.raise_for_status()
    messages = parse_public_html(response.text)
    hidden = not messages and "/s/" not in str(response.url)
    return messages, hidden


def fetch_public(username: str) -> list[dict]:
    messages, _hidden = inspect_public(username)
    return messages


def same_channel(chat: dict, channel: str) -> bool:
    username = username_of(channel)
    if username and str(chat.get("username") or "").lower() == username.lower():
        return True
    raw = channel.strip()
    return raw.startswith("-") and str(chat.get("id")) == raw


def messages_from_updates(payload: dict, channel: str) -> tuple[list[dict], int | None]:
    rows = []
    offset = None
    for update in payload.get("result") or []:
        offset = max(offset or 0, int(update["update_id"]) + 1)
        post = update.get("channel_post") or {}
        chat = post.get("chat") or {}
        text = post.get("text") or post.get("caption") or ""
        if not text or not same_channel(chat, channel) or "date" not in post:
            continue
        moment = datetime.fromtimestamp(int(post["date"]), tz=timezone.utc)
        rows.append({"text": text, "message_at": moment, "message_id": post.get("message_id")})
    return rows, offset


def inbox_path():
    return repo_root() / "memory" / "ads-inbox.json"


def read_inbox() -> list[dict]:
    path = inbox_path()
    if not path.exists():
        return []
    return read_json(path).get("messages") or []


def save_inbox(messages: list[dict]) -> None:
    stored = []
    for message in messages:
        moment = message["message_at"]
        stored.append(
            {
                "text": message["text"],
                "message_at": iso(moment) if not isinstance(moment, str) else moment,
                "message_id": message.get("message_id"),
            }
        )
    write_json(inbox_path(), {"messages": stored[-80:]})


def pull_bot_updates(channel: str) -> list[dict]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return []
    response = httpx.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={"limit": 100, "timeout": 0, "allowed_updates": '["channel_post"]'},
        timeout=20,
    )
    response.raise_for_status()
    fresh, offset = messages_from_updates(response.json(), channel)
    known = {item.get("message_id"): item for item in read_inbox()}
    for item in fresh:
        known[item.get("message_id")] = {
            "text": item["text"],
            "message_at": iso(item["message_at"]),
            "message_id": item.get("message_id"),
        }
    merged = list(known.values())
    save_inbox(merged)
    if offset:
        httpx.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 0},
            timeout=20,
        )
    return normalize_messages(merged)


def fetch_telethon(channel: str) -> list[dict]:
    from telethon.sessions import StringSession
    from telethon.sync import TelegramClient

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session = os.environ["TELEGRAM_STRING_SESSION"]
    with TelegramClient(StringSession(session), api_id, api_hash) as client:
        rows = []
        for message in client.iter_messages(channel, limit=40):
            if not getattr(message, "message", None):
                continue
            rows.append({"text": message.message, "message_at": message.date})
        return rows


def load_messages(channel: str) -> tuple[list[dict], str]:
    session = os.environ.get("TELEGRAM_STRING_SESSION", "").strip()
    username = username_of(channel)
    public: list[dict] = []
    hidden = False
    if username:
        public, hidden = inspect_public(username)
    if public:
        return public, "web"
    if session and os.environ.get("TELEGRAM_API_ID") and os.environ.get("TELEGRAM_API_HASH"):
        return fetch_telethon(channel), "telethon"
    if os.environ.get("TELEGRAM_BOT_TOKEN", "").strip():
        bot_messages = pull_bot_updates(channel)
        if bot_messages:
            return bot_messages, "bot"
        if hidden:
            raise RuntimeError(
                "Канал рекламы скрывает историю. Бот в канале есть, но старые посты Telegram не отдаёт. "
                "Опубликуйте расписание ещё раз после добавления бота."
            )
    if username and not hidden:
        return [], "web"
    raise RuntimeError("ADS_CHANNEL is private and TELEGRAM_STRING_SESSION is not configured")


def delete_scheduled(chat: str, message_id: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not chat or not message_id:
        return False
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/deleteMessage",
        data={"chat_id": chat, "message_id": message_id},
        timeout=20,
    )
    if response.status_code != 200:
        return False
    return bool(response.json().get("ok"))


def normalize_messages(messages: list[dict]) -> list[dict]:
    normalized = []
    for message in messages:
        moment = message["message_at"]
        if isinstance(moment, str):
            moment = parse_iso(moment)
        normalized.append({"text": message["text"], "message_at": moment})
    return normalized
