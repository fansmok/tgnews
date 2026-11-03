"""Telethon-клиент user-аккаунта: отложка и premium custom emoji.

Cloud-VM выпускает наружу только HTTP(S) через прокси, сырой MTProto/TCP там рвётся.
MTProto поверх HTTP (POST /api) проходит, поэтому транспорт выбирается через
TELEGRAM_TRANSPORT=http|tcp|auto (auto: сначала http, затем tcp).
"""
from __future__ import annotations

import asyncio
import os

from telethon.network.connection.connection import Connection, PacketCodec
from telethon.network.connection.tcpfull import ConnectionTcpFull
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

HTTP_PORT = 80


class _NoCodec(PacketCodec):
    tag = None
    obfuscate_tag = None

    def encode_packet(self, data):
        return data

    async def read_packet(self, reader):
        raise NotImplementedError


class ConnectionHttpPool(Connection):
    """MTProto over HTTP: каждый пакет — отдельный POST /api.

    Telegram держит ответ на POST без готовых данных (long-poll). На одном keep-alive
    соединении это блокирует все следующие ответы, поэтому запросы идут параллельно
    через пул, а тела ответов складываются в общую очередь. Встроенный
    HttpPacketCodec Telethon не годится: он сравнивает line[-1] (int) с b"\\n".
    """

    packet_codec = _NoCodec

    async def _connect(self, timeout=None, ssl=None):
        import httpx

        self._codec = self.packet_codec(self)
        self._url = f"http://{self._ip}:{self._port}/api"
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=timeout or 20),
            limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
            headers={"Content-Type": "application/octet-stream"},
        )
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._posts: set[asyncio.Task] = set()

    async def disconnect(self):
        if not self._connected:
            return
        for task in list(getattr(self, "_posts", ())):
            task.cancel()
        await super().disconnect()
        http = getattr(self, "_http", None)
        if http is not None:
            await http.aclose()

    async def _post(self, data: bytes):
        try:
            response = await self._http.post(self._url, content=data)
            response.raise_for_status()
            if response.content:
                await self._inbox.put((response.content, None))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            await self._inbox.put((None, exc))

    async def _send_loop(self):
        try:
            while self._connected:
                data = await self._send_queue.get()
                task = asyncio.ensure_future(self._post(data))
                self._posts.add(task)
                task.add_done_callback(self._posts.discard)
        except asyncio.CancelledError:
            pass

    async def _recv(self):
        data, error = await self._inbox.get()
        if error is not None:
            raise IOError(str(error)) from error
        return data


def _proxy():
    proxy = os.environ.get("TELEGRAM_PROXY", "").strip()
    if not proxy:
        return None
    cleaned = proxy.replace("socks5://", "")
    host, _, port = cleaned.partition(":")
    return ("socks5", host, int(port or "1080"))


def _client(transport: str, session: str | None = None) -> TelegramClient:
    string = StringSession(session if session is not None else os.environ["TELEGRAM_STRING_SESSION"])
    connection = ConnectionTcpFull
    if transport == "http":
        connection = ConnectionHttpPool
        if string.server_address:
            string.set_dc(string.dc_id, string.server_address, HTTP_PORT)
    return TelegramClient(
        string,
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"],
        connection=connection,
        proxy=_proxy(),
        connection_retries=1,
        retry_delay=1,
        auto_reconnect=False,
        timeout=20,
    )


def transports() -> list[str]:
    wanted = os.environ.get("TELEGRAM_TRANSPORT", "auto").strip().lower() or "auto"
    if wanted in {"http", "tcp"}:
        return [wanted]
    return ["http", "tcp"]


def connect_user(session: str | None = None, attempts: int = 2) -> TelegramClient:
    last: Exception | None = None
    for _ in range(attempts):
        for transport in transports():
            client = _client(transport, session)
            try:
                client.connect()
                if client.is_connected() and (session == "" or client.is_user_authorized()):
                    return client
                last = PermissionError("user session is not authorized")
            except Exception as exc:  # noqa: BLE001
                last = exc
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001
                pass
    raise ConnectionError(f"Telethon did not connect: {last}")


def resolve_chat(client: TelegramClient, chat: str):
    target = int(chat) if chat.lstrip("-").isdigit() else chat
    try:
        return client.get_input_entity(target)
    except ValueError:
        client.get_dialogs()
        return client.get_input_entity(target)


def _entities(items: list[dict]) -> list:
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
    for item in items:
        if item["type"] == "custom_emoji":
            formatted.append(MessageEntityCustomEmoji(item["offset"], item["length"], int(item["custom_emoji_id"])))
        else:
            formatted.append(mapping[item["type"]](item["offset"], item["length"]))
    return formatted


def send_photo(chat: str, photo: str, plain: str, entities: list[dict], schedule_at=None):
    """Одна попытка отправки после успешного connect: повтор send мог бы задвоить пост."""
    client = connect_user()
    try:
        peer = resolve_chat(client, chat)
        kwargs = {"caption": plain, "formatting_entities": _entities(entities)}
        if schedule_at is not None:
            kwargs["schedule"] = schedule_at
        return client.send_file(peer, photo, **kwargs)
    finally:
        client.disconnect()


def _read_retry(read):
    """Только для чтения: повтор безопасен, в отличие от send."""
    import functools
    import time

    @functools.wraps(read)
    def wrapper(*args, **kwargs):
        last: Exception | None = None
        for attempt in range(3):
            try:
                return read(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(1 + attempt)
        raise last

    return wrapper


@_read_retry
def scheduled_messages(chat: str) -> list:
    from telethon import functions

    client = connect_user()
    try:
        peer = resolve_chat(client, chat)
        result = client(functions.messages.GetScheduledHistoryRequest(peer=peer, hash=0))
        return list(result.messages)
    finally:
        client.disconnect()


@_read_retry
def channel_posts(chat: str, hours: int = 36) -> list[dict]:
    """Лента и отложка канала: источник правды для дедупа, даже если news.db сброшена."""
    from datetime import datetime, timedelta, timezone

    from telethon import functions

    client = connect_user()
    try:
        peer = resolve_chat(client, chat)
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        posts = []
        for message in client.iter_messages(peer, limit=80):
            if message.date < since:
                break
            if message.message:
                posts.append({"id": message.id, "text": message.message, "date": message.date, "scheduled": False})
        scheduled = client(functions.messages.GetScheduledHistoryRequest(peer=peer, hash=0))
        for message in scheduled.messages:
            if getattr(message, "message", None):
                posts.append({"id": message.id, "text": message.message, "date": message.date, "scheduled": True})
        return posts
    finally:
        client.disconnect()


def delete_messages(chat: str, ids: list[int], scheduled: bool = False) -> None:
    from telethon import functions

    client = connect_user()
    try:
        peer = resolve_chat(client, chat)
        if scheduled:
            client(functions.messages.DeleteScheduledMessagesRequest(peer=peer, id=ids))
        else:
            client.delete_messages(peer, ids)
    finally:
        client.disconnect()
