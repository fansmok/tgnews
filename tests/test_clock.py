from datetime import datetime, timedelta, timezone

import httpx

from newsagent import runtime


MSK = runtime.MSK


def test_now_msk_adds_measured_offset(monkeypatch):
    fixed = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(runtime, "_OFFSET", timedelta(hours=4))
    monkeypatch.setattr(runtime, "utc_now", lambda: fixed)
    assert runtime.now_msk() == datetime(2026, 10, 22, 13, 0, tzinfo=MSK)


def test_small_skew_is_ignored(monkeypatch):
    monkeypatch.setattr(runtime, "utc_now", lambda: datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc))

    class Response:
        headers = {"date": "Thu, 22 Oct 2026 10:00:20 GMT"}

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: Response())
    assert runtime.measure_clock_offset() == timedelta(0)
    assert runtime._CLOCK_STATUS == "ok"


def test_large_skew_is_kept(monkeypatch):
    monkeypatch.setattr(runtime, "utc_now", lambda: datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc))

    class Response:
        headers = {"date": "Thu, 22 Oct 2026 10:00:00 GMT"}

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: Response())
    assert runtime.measure_clock_offset() == timedelta(hours=4)
    assert runtime._CLOCK_STATUS == "corrected"
