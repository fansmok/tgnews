from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

ROOT = "https://generativelanguage.googleapis.com/v1beta"
PREFERRED = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)


class GeminiUnavailable(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiUnavailable("GEMINI_API_KEY is empty")
    return key


def _headers() -> dict[str, str]:
    return {"x-goog-api-key": _key(), "Content-Type": "application/json"}


def list_flash_models() -> list[str]:
    response = httpx.get(f"{ROOT}/models", headers=_headers(), timeout=20)
    if response.status_code in (401, 403):
        raise GeminiUnavailable(f"auth {response.status_code}")
    if response.status_code >= 400:
        raise GeminiUnavailable(f"models {response.status_code}")
    names: list[str] = []
    for item in response.json().get("models") or []:
        methods = item.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        name = str(item.get("name") or "").removeprefix("models/")
        if not name or any(skip in name for skip in ("image", "tts", "embedding", "live")):
            continue
        names.append(name)
    flash = [name for name in names if "flash" in name]
    return flash or names


def model_order() -> list[str]:
    chosen = os.environ.get("GEMINI_MODEL", "").strip()
    ordered: list[str] = []
    for name in ((chosen,) if chosen else ()) + PREFERRED:
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def _candidate_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise GeminiUnavailable("empty candidates")
    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    texts = [str(part.get("text") or "") for part in parts if part.get("text")]
    if not texts:
        raise GeminiUnavailable("empty text")
    return "\n".join(texts)


def generate_json(prompt: str, schema: dict[str, Any], *, temperature: float) -> tuple[dict[str, Any], str]:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    models = model_order()
    listed = False
    last = "no model"
    index = 0
    while index < len(models):
        model = models[index]
        index += 1
        for attempt in range(3):
            try:
                response = httpx.post(
                    f"{ROOT}/models/{model}:generateContent",
                    headers=_headers(),
                    json=body,
                    timeout=45,
                )
            except httpx.HTTPError as exc:
                last = type(exc).__name__
                time.sleep(0.4 * (attempt + 1))
                continue
            if response.status_code in (429, 408, 500, 502, 503, 504):
                last = f"{model} {response.status_code}"
                time.sleep(0.4 * (attempt + 1))
                continue
            if response.status_code in (401, 403):
                raise GeminiUnavailable(f"auth {response.status_code}")
            if response.status_code == 404 and not listed:
                listed = True
                for name in list_flash_models():
                    if name not in models:
                        models.append(name)
                last = f"{model} 404"
                break
            if response.status_code >= 400:
                last = f"{model} {response.status_code}"
                break
            data = json.loads(_candidate_text(response.json()))
            if not isinstance(data, dict):
                raise GeminiUnavailable("json is not an object")
            return data, model
    raise GeminiUnavailable(last)
