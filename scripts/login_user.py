#!/usr/bin/env python3
"""Вход в Premium-аккаунт. Строка сессии пишется только в .env, не в вывод."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.runtime import load_dotenv  # noqa: E402

ENV_PATH = ROOT / ".env"


def _upsert(key: str, value: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    found = False
    updated = []
    for line in lines:
        if line.startswith(f"{key}="):
            updated.append(f"{key}={value}")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"{key}={value}")
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=ENV_PATH.parent,
        prefix=".env.",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write("\n".join(updated) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, ENV_PATH)
    finally:
        temp_path.unlink(missing_ok=True)


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR {name} is empty")
        raise SystemExit(1)
    return value


def _client():
    from telethon.sessions import StringSession
    from telethon.sync import TelegramClient

    api_id = int(_require("TELEGRAM_API_ID"))
    api_hash = _require("TELEGRAM_API_HASH")
    saved = os.environ.get("TELEGRAM_LOGIN_SESSION", "").strip()
    return TelegramClient(StringSession(saved), api_id, api_hash)


def _remember(client) -> None:
    _upsert("TELEGRAM_LOGIN_SESSION", client.session.save())


def send_code() -> int:
    phone = _require("TELEGRAM_PHONE")
    os.environ["TELEGRAM_LOGIN_SESSION"] = ""
    client = _client()
    client.connect()
    try:
        sent = client.send_code_request(phone)
        _remember(client)
        _upsert("TELEGRAM_PHONE_CODE_HASH", sent.phone_code_hash)
    finally:
        client.disconnect()
    print("code_sent")
    return 0


def _authorized_name(client) -> str:
    me = client.get_me()
    _upsert("TELEGRAM_STRING_SESSION", client.session.save())
    _upsert("PUBLISH_BACKEND", "user")
    _upsert("TELEGRAM_PHONE_CODE_HASH", "")
    _upsert("TELEGRAM_LOGIN_SESSION", "")
    return f"@{me.username}" if me and me.username else "account"


def finish(code: str) -> int:
    phone = _require("TELEGRAM_PHONE")
    phone_code_hash = _require("TELEGRAM_PHONE_CODE_HASH")
    _require("TELEGRAM_LOGIN_SESSION")
    from telethon.errors import PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError

    client = _client()
    client.connect()
    try:
        try:
            client.sign_in(phone, code.strip(), phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            _remember(client)
            print("ERROR cloud password required")
            return 2
        except (PhoneCodeExpiredError, PhoneCodeInvalidError):
            print("ERROR code rejected")
            return 1
        username = _authorized_name(client)
    finally:
        client.disconnect()
    print(f"session_saved {username}")
    return 0


def finish_password(password: str) -> int:
    _require("TELEGRAM_LOGIN_SESSION")
    client = _client()
    client.connect()
    try:
        client.sign_in(password=password)
        username = _authorized_name(client)
    finally:
        client.disconnect()
    print(f"session_saved {username}")
    return 0


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--code")
    parser.add_argument("--password")
    args = parser.parse_args()
    if args.send:
        return send_code()
    if args.code:
        return finish(args.code)
    if args.password:
        return finish_password(args.password)
    print("usage: login_user.py --send | --code <code>")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
