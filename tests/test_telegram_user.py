import asyncio

from newsagent import telegram_user


def test_transport_order_prefers_http_on_auto(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TRANSPORT", raising=False)
    assert telegram_user.transports() == ["http", "tcp"]
    monkeypatch.setenv("TELEGRAM_TRANSPORT", "tcp")
    assert telegram_user.transports() == ["tcp"]


def test_http_pool_posts_independently_and_queues_bodies():
    class FakeResponse:
        def __init__(self, body):
            self.content = body

        def raise_for_status(self):
            return None

    class FakeHttp:
        def __init__(self):
            self.release = asyncio.Event()

        async def post(self, url, content):
            if content == b"held":
                await self.release.wait()
            return FakeResponse(b"reply:" + content)

    async def scenario():
        conn = telegram_user.ConnectionHttpPool.__new__(telegram_user.ConnectionHttpPool)
        conn._http = FakeHttp()
        conn._url = "http://example/api"
        conn._inbox = asyncio.Queue()
        conn._posts = set()
        held = asyncio.ensure_future(conn._post(b"held"))
        quick = asyncio.ensure_future(conn._post(b"quick"))
        first = await asyncio.wait_for(conn._recv(), 1)
        conn._http.release.set()
        second = await asyncio.wait_for(conn._recv(), 1)
        await asyncio.gather(held, quick)
        return first, second

    first, second = asyncio.run(scenario())
    assert first == b"reply:quick"
    assert second == b"reply:held"
