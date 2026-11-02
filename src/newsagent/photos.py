from __future__ import annotations

import io
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
BAD_URL = re.compile(r"logo|sprite|favicon|avatar|placeholder|1x1|pixel|doubleclick|adservice|banner|stitcher", re.IGNORECASE)
LOGO_NEGATION = re.compile(r"(?:^|[^A-Za-z0-9])(?:no|without)[_-]?logo", re.IGNORECASE)
MIN_BYTES = 15_000
MIN_SIDE = 320
MAX_BYTES = 5_000_000


def extract_og_image(page_url: str, html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    for attrs in (
        {"property": "og:image"},
        {"name": "twitter:image"},
        {"property": "og:image:url"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return urljoin(page_url, tag["content"].strip())
    return None


def url_blocked(url: str) -> bool:
    cleaned = LOGO_NEGATION.sub(" ", url)
    return BAD_URL.search(cleaned) is not None


def acceptable(url: str, payload: bytes) -> tuple[bool, str, int, int]:
    if url_blocked(url):
        return False, "bad_url", 0, 0
    if not MIN_BYTES <= len(payload) <= MAX_BYTES:
        return False, "bad_size", 0, 0
    if not (payload.startswith(b"\xff\xd8") or payload.startswith(b"\x89PNG") or payload.startswith(b"RIFF")):
        return False, "bad_magic", 0, 0
    try:
        image = Image.open(io.BytesIO(payload))
        image.verify()
        image = Image.open(io.BytesIO(payload))
        width, height = image.size
    except (UnidentifiedImageError, OSError):
        return False, "bad_image", 0, 0
    if min(width, height) < MIN_SIDE:
        return False, "too_small", width, height
    if width / height > 3 or height / width > 3:
        return False, "banner", width, height
    return True, "ok", width, height


def extension(payload: bytes) -> str:
    if payload.startswith(b"\xff\xd8"):
        return "jpg"
    if payload.startswith(b"\x89PNG"):
        return "png"
    return "webp"
