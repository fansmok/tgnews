import json

import httpx

from newsagent import gemini
from newsagent.gemini import GeminiUnavailable


def test_generate_json_reads_model_text(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    class Response:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps({"title": "Гол"}, ensure_ascii=False)}]}}
                ]
            }

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: Response())
    data, model = gemini.generate_json("привет", {"type": "OBJECT"}, temperature=0.2)
    assert data["title"] == "Гол"
    assert model == "gemini-test"


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    try:
        gemini.generate_json("привет", {"type": "OBJECT"}, temperature=0.2)
    except GeminiUnavailable as exc:
        assert "GEMINI_API_KEY" in str(exc)
    else:
        raise AssertionError("expected GeminiUnavailable")
