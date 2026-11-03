from __future__ import annotations

import html as html_lib
from pathlib import Path

from PIL import Image

from newsagent.caption import contains_ad, longest_common_run, mostly_cyrillic, render_post
from newsagent.copytext import reaction_missing_words, repeats_quote, restates_title, statement_missing_content
from newsagent.emoji_sync import ALLOWED_PACKS
from newsagent.reactions import has_foreign_emoji, mismatched_reaction
from newsagent.lexicon import load_lexicon
from newsagent.runtime import read_json

GENERIC_TAGS = {
    "football",
    "trophy",
    "quote",
    "conflict",
    "record",
    "news",
    "goal",
    "injury",
    "transfer",
    "contract",
    "red-card",
    "yellow-card",
    "penalty",
    "referee",
    "var",
    "debut",
    "sack",
    "lineup",
    "result",
}


def _fail(checks: dict, key: str, detail: str) -> None:
    checks[key] = {"status": "FAIL", "detail": detail}


def _ok(checks: dict, key: str, detail: str = "ok") -> None:
    checks[key] = {"status": "PASS", "detail": detail}


def machine_check(run_dir: Path) -> dict:
    checks: dict[str, dict] = {}
    required = [
        "story.json",
        "copy.json",
        "emoji.json",
        "voice.json",
        "photo.json",
        "design.json",
        "photo-review.json",
        "slot-plan.json",
        "memory-decision.json",
    ]
    for name in required:
        if not (run_dir / name).exists():
            _fail(checks, name, "missing")
        else:
            _ok(checks, name)
    if any(item["status"] == "FAIL" for item in checks.values()):
        return {"status": "FAIL", "checks": checks}

    story = read_json(run_dir / "story.json")
    copy = read_json(run_dir / "copy.json")
    emoji = read_json(run_dir / "emoji.json")
    voice = read_json(run_dir / "voice.json")
    photo = read_json(run_dir / "photo.json")
    design = read_json(run_dir / "design.json")
    photo_review = read_json(run_dir / "photo-review.json")
    plan = read_json(run_dir / "slot-plan.json")
    memory = read_json(run_dir / "memory-decision.json")
    lexicon = load_lexicon()
    club_ids = {item["id"] for item in lexicon["clubs"]}

    if memory.get("duplicate"):
        _fail(checks, "memory", "story already published")
    else:
        _ok(checks, "memory")

    title = (copy.get("title") or "").strip()
    paragraphs = [part.strip() for part in copy.get("paragraphs") or [] if part and part.strip()]
    if not title or len(title) > 120:
        _fail(checks, "title", "empty or longer than 120")
    else:
        _ok(checks, "title")
    if len(paragraphs) > 4 or any(len(part) > 320 for part in paragraphs):
        _fail(checks, "paragraphs", "too many or a paragraph is longer than 320")
    elif any(restates_title(title, part) for part in paragraphs):
        _fail(checks, "paragraphs", "paragraph repeats the title")
    else:
        _ok(checks, "paragraphs", str(len(paragraphs)))

    source_text = " ".join(
        part for part in (story.get("title"), story.get("summary"), copy.get("source_text")) if part
    )
    rewritten = " ".join([title, *paragraphs, (copy.get("quote") or {}).get("text") or ""])
    if contains_ad(rewritten) or contains_ad(voice.get("comment") or ""):
        _fail(checks, "ads_in_text", "promo or ad wording")
    else:
        _ok(checks, "ads_in_text")
    run = longest_common_run(source_text, rewritten)
    if mostly_cyrillic(source_text):
        _ok(checks, "plagiarism", "russian source, light edit")
    elif run >= 7:
        _fail(checks, "plagiarism", f"common word run {run}")
    else:
        _ok(checks, "plagiarism", f"run {run}")
    comment = (voice.get("comment") or "").strip()
    if comment and has_foreign_emoji(comment):
        _fail(checks, "comment", "emoji outside the reaction list")
    elif comment and mismatched_reaction(comment):
        _fail(checks, "comment", f"смеющийся знак под согласием: {mismatched_reaction(comment)}")
    elif comment and len(comment) > 220:
        _fail(checks, "comment", "longer than 220")
    else:
        _ok(checks, "comment", "none" if not comment else str(len(comment)))

    quote = copy.get("quote")
    quote_text = (quote or {}).get("text") or ""
    if repeats_quote(title, paragraphs, quote_text):
        _fail(checks, "repeat", "quote is already in the title or paragraph")
    elif any(restates_title(title, part) for part in paragraphs):
        _fail(checks, "repeat", "paragraph repeats the title")
    else:
        _ok(checks, "repeat")
    missing_speaker = reaction_missing_words(title, paragraphs, quote if isinstance(quote, dict) else None)
    if missing_speaker:
        _fail(checks, "reaction", f"нет слов {missing_speaker}")
    elif statement_missing_content(title, paragraphs, quote if isinstance(quote, dict) else None):
        _fail(checks, "reaction", "заявление без содержания: не сказано, что заявлено")
    else:
        _ok(checks, "reaction")
    if quote:
        text = quote_text.strip()
        if not text or text[0] in "\"“”":
            _fail(checks, "quote", "quote must use guillemets at render time and have text")
        else:
            _ok(checks, "quote")
    else:
        _ok(checks, "quote", "none")

    photo_path = run_dir / (photo.get("file") or "")
    if photo.get("status") != "ok" or not photo_path.exists():
        _fail(checks, "photo", "missing image file")
    elif int(photo.get("width") or 0) < 320 or int(photo.get("height") or 0) < 320:
        _fail(checks, "photo", "image too small")
    else:
        _ok(checks, "photo")

    design_path = run_dir / (design.get("file") or "")
    if design.get("status") != "ok" or not design_path.exists():
        _fail(checks, "design", "missing designed image")
    else:
        try:
            with Image.open(design_path) as image:
                size = image.size
        except Exception:
            _fail(checks, "design", "designed image cannot be opened")
        else:
            if size != (600, 600):
                _fail(checks, "design", f"designed image is {size[0]}x{size[1]}, expected 600x600")
            else:
                _ok(checks, "design", "600x600")
    if photo_review.get("verdict") != "PASS":
        _fail(checks, "photo_review", "photo review is missing or not PASS")
    else:
        _ok(checks, "photo_review")

    raw_title_emoji = emoji.get("title_emoji") or {}
    title_emojis = raw_title_emoji if isinstance(raw_title_emoji, list) else [raw_title_emoji]
    all_title_tags: set[str] = set()
    for idx, title_emoji in enumerate(title_emojis):
        emoji_id = str(title_emoji.get("custom_emoji_id") or "")
        tags = set(title_emoji.get("tags") or [])
        all_title_tags |= tags
        set_name = title_emoji.get("set_name") or ""
        check_name = "emoji" if len(title_emojis) == 1 else f"emoji_{idx}"
        if set_name == "unicode_fallback" and not emoji_id:
            _ok(checks, check_name)
            all_title_tags |= tags
            continue
        if set_name not in ALLOWED_PACKS:
            _fail(checks, check_name, "emoji pack is not allowed")
        elif not emoji_id.isdigit():
            _fail(checks, check_name, "title custom emoji id missing")
        elif not tags:
            _fail(checks, check_name, "emoji has no tags")
        else:
            wrong = (tags & club_ids) - set(story.get("clubs") or [])
            allowed = set(story.get("clubs") or []) | set(story.get("competitions") or []) | GENERIC_TAGS | {story.get("action") or ""}
            club_pack = set_name == "FC_logos"
            if wrong:
                _fail(checks, check_name, "emoji belongs to another club")
            elif club_pack and not (tags & (set(story.get("clubs") or []) | set(story.get("competitions") or []))):
                _fail(checks, check_name, "club pack emoji is not tagged for this club")
            elif not (tags & allowed):
                _fail(checks, check_name, "emoji does not match the story")
            else:
                _ok(checks, check_name)

    catalog_path = Path(__file__).resolve().parents[2] / "shared" / "emoji-catalog.json"
    catalog = read_json(catalog_path) if catalog_path.exists() else {"items": []}
    available = set()
    for item in catalog.get("items") or []:
        available |= set(item.get("tags") or []) & club_ids
    needed = {club for club in (story.get("clubs") or []) if club in available}
    if needed and not (all_title_tags & needed):
        _fail(checks, "emoji_club_needed", "catalog has a club emoji that was not used")
    elif len(title_emojis) > 1 and needed:
        _ok(checks, "emoji_club_needed")

    for index, item in enumerate(emoji.get("paragraph_emoji") or []):
        if not item:
            continue
        item_tags = set(item.get("tags") or [])
        if item.get("set_name") not in ALLOWED_PACKS or not str(item.get("custom_emoji_id") or "").isdigit():
            _fail(checks, f"paragraph_emoji_{index}", "emoji pack is not allowed")
        else:
            wrong = (item_tags & club_ids) - set(story.get("clubs") or [])
            if wrong:
                _fail(checks, f"paragraph_emoji_{index}", "wrong club")
            else:
                _ok(checks, f"paragraph_emoji_{index}")

    post = {
        "title": title,
        "paragraphs": paragraphs,
        "bold_spans": copy.get("bold_spans") or [],
        "quote": quote,
        "comment": voice.get("comment"),
        "title_emoji": raw_title_emoji,
        "paragraph_emoji": emoji.get("paragraph_emoji") or [],
    }
    rendered = render_post(post)
    expected_title = f"<b>{html_lib.escape(title)}</b>"
    has_custom = any(str(te.get("custom_emoji_id") or "").isdigit() for te in title_emojis)
    if expected_title not in rendered["html"]:
        _fail(checks, "bold_title", "title is not bold")
    elif rendered["utf16_length"] > 1000:
        _fail(checks, "length", str(rendered["utf16_length"]))
    elif has_custom and "tg-emoji" not in rendered["html"]:
        _fail(checks, "emoji_render", "custom emoji tag missing")
    elif not emoji_id and (title_emoji.get("fallback") or "") not in rendered["html"]:
        _fail(checks, "emoji_render", "standard emoji missing from caption")
    else:
        _ok(checks, "caption", str(rendered["visible_length"]))
        if quote and ("<blockquote>" not in rendered["html"] or "«" not in rendered["html"]):
            _fail(checks, "quote_render", "instagram quote markup missing")
        else:
            _ok(checks, "quote_render")

    body = " ".join(paragraphs)
    bold_needed = [span for span in (copy.get("bold_spans") or []) if span]
    if not body:
        _ok(checks, "bold_spans", "title only")
    elif not bold_needed or any(span not in body for span in bold_needed):
        _fail(checks, "bold_spans", "put at least one key fact in the body and mark it")
    else:
        _ok(checks, "bold_spans")

    if not plan.get("publish_at"):
        _fail(checks, "slot", "no publish_at")
    else:
        _ok(checks, "slot", plan.get("reason") or "")

    status = "PASS" if all(item["status"] == "PASS" for item in checks.values()) else "FAIL"
    return {"status": status, "checks": checks, "caption": rendered}
