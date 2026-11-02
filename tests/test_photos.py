import io
import os

from PIL import Image

from newsagent.photos import acceptable


def _jpeg(width: int = 400, height: int = 320) -> bytes:
    image = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def test_no_logo_filename_is_not_a_bad_url():
    payload = _jpeg()
    ok, reason, width, height = acceptable(
        "https://www.sports.ru/dynamic_images/news/111/741/029/1/share/79b8a6_no_logo_no_text.jpg",
        payload,
    )
    assert ok is True
    assert reason == "ok"
    assert (width, height) == (400, 320)


def test_negated_logo_names_are_not_a_bad_url():
    payload = b"x"
    for url in (
        "https://cdn.example.com/photos/nologo.jpg",
        "https://cdn.example.com/photos/no-logo-share.png",
        "https://cdn.example.com/photos/without_logo.webp",
    ):
        _, reason, _, _ = acceptable(url, payload)
        assert reason != "bad_url"


def test_real_logo_url_is_rejected():
    ok, reason, _, _ = acceptable("https://cdn.example.com/clubs/logo.png", _jpeg())
    assert ok is False
    assert reason == "bad_url"


def test_logo_word_inside_another_token_is_still_rejected():
    _, reason, _, _ = acceptable("https://cdn.example.com/know_logo.png", b"x")
    assert reason == "bad_url"


def test_stitcher_url_is_rejected():
    ok, reason, _, _ = acceptable("https://a.espncdn.com/combiner/i?img=/i/stitcher/default.png", _jpeg())
    assert ok is False
    assert reason == "bad_url"

