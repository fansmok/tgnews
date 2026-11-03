from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from newsagent.runtime import read_json, repo_root

GREEN = (11, 93, 40, 255)
YELLOW = (255, 209, 0, 255)
BLACK = (11, 11, 13, 255)
WHITE = (255, 255, 255, 255)
RED = (225, 6, 0, 255)
INSIDER = (31, 175, 56, 255)
PANEL = (19, 63, 39, 255)
SOFT = (214, 216, 214, 255)
LIGHT = (232, 232, 232, 255)

BADGE_FILL = {
    "news": YELLOW,
    "transfer": (24, 24, 24, 255),
    "insider": INSIDER,
    "urgent": RED,
}
BADGE_INK = {
    "news": BLACK,
    "transfer": WHITE,
    "insider": WHITE,
    "urgent": WHITE,
}
PHOTO_LED = {"main", "urgent", "transfer", "insider", "scandal", "meme"}
STRIPED = {"main", "transfer", "insider", "meme"}


def brand_spec() -> dict:
    return read_json(repo_root() / "shared" / "brand.json")


def pillow_footer(_story: dict | None = None) -> str:
    """Запасная карточка Pillow подписывается брендом, а не id источника."""
    return "GOL88.RU"


def font(role: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    spec = brand_spec()["fonts"]
    path = repo_root() / spec.get(role, spec["text"])
    if path.exists():
        return ImageFont.truetype(str(path), size=max(8, size))
    return ImageFont.load_default()


_DECLINES_MOVE = re.compile(
    r"не будет искать|не ищет|не станет искать|"
    r"не будет покупать|не собира\w* покупать|не планир\w* покупать|не планир\w* искать|"
    r"не будет подписывать|"
    r"отказал\w* от (?:покупки|поиска|трансфера)|"
    r"не интересу\w* покупк|"
    r"not looking for|will not (?:buy|sign)|won'?t (?:buy|sign)|"
    r"no plans to (?:sign|buy)|ruled out (?:a )?(?:move|signing|deal)",
    re.IGNORECASE,
)
_FEE = re.compile(
    r"\d+(?:[\s\u00a0]\d+)?(?:[,.]\d+)?\s*(?:млн|миллион\w*|млрд|€|евро|£|\$)",
    re.IGNORECASE,
)
_DEAL = re.compile(
    r"подписал|подпишет|подпишут|переш[её]л|перейд[её]т|арендовал|арендует|(?<![а-яё])купил|"
    r"согласовал\w* переход|\bsigns\b|\bsigned\b",
    re.IGNORECASE,
)


_TRANSFER_SIGNAL = re.compile(
    r"трансфер|(?<![а-яё])переход(?:а|е|ом|у)?(?![а-яё])|перейд[её]т|переш[её]л|аренд|"
    r"интерес\w*|следит за|хоч\w* (?:подписать|купить|забрать|оформить)|переговор|предложени\w* за|"
    r"\btransfers?\b|\bbid\b|\boffer\b|\binterest(?:ed)?\b|\btalks\b|\bmove to\b|\bloan\b|\bsign(?:s|ed|ing)?\b",
    re.IGNORECASE,
)


def _card_text(story: dict, copy: dict | None) -> str:
    copy = copy or {}
    parts = [
        (story or {}).get("title") or "",
        (story or {}).get("summary") or "",
        copy.get("title") or "",
        " ".join(str(part) for part in (copy.get("paragraphs") or []) if part),
    ]
    return " ".join(part for part in parts if part).replace("ё", "е")


def pick_template(story: dict, copy: dict | None) -> str:
    action = (story or {}).get("action") or ""
    title = ((story or {}).get("title") or "").lower()
    if action == "result" and any(word in title for word in ("трансляц", " live", "live ")) and not re.search(r"\d\s*[:\-–]\s*\d", title):
        return "fixture"
    if action == "result":
        return "result"
    if action == "lineup":
        return "fixture"
    if action == "transfer":
        # «ТРАНСФЕР» на карточке — только при явном трансферном сигнале; сомнение — «НОВОСТЬ».
        blob = _card_text(story, copy)
        signal = _TRANSFER_SIGNAL.search(blob) or _FEE.search(blob) or _DEAL.search(blob)
        declined = _DECLINES_MOVE.search(blob) and not _FEE.search(blob) and not _DEAL.search(blob)
        if signal and not declined:
            return "transfer"
    if action in {"sack", "injury"}:
        return "urgent"
    if action == "scandal":
        return "scandal"
    if copy and (copy.get("quote") or {}).get("text"):
        return "quote"
    return "main"


def boxes_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def _kind_layout(kind: str, width: int, height: int) -> dict:
    if kind == "portrait":
        split = int(height * 0.62)
        photo = (0, 0, width, split)
    else:
        split = int(height * 0.58)
        photo = (0, 0, width, height)
    panel = (0, split, width, height - split)
    margin = max(18, width // 36)
    logo_size = max(56, int(min(width, height) * 0.1))
    logo = (margin, height - margin - logo_size, logo_size, logo_size)
    badge_h = max(36, height // 18)
    badge = (margin, margin, int(width * 0.34), badge_h)
    footer = (
        logo[0] + logo_size + margin // 2,
        logo[1],
        width - (logo[0] + logo_size + margin // 2) - margin,
        logo_size,
    )
    headline = (margin, panel[1] + margin // 3, width - margin * 2, max(48, logo[1] - panel[1] - margin))
    return {"photo": photo, "panel": panel, "badge": badge, "logo": logo, "headline": headline, "footer": footer}


def choose_size(src_w: int, src_h: int, kind_preference: str = "square") -> dict:
    """Все посты выходят квадратом 600×600. Кадр вписывается в это окно."""
    item = brand_spec()["sizes"][0]
    width, height = int(item["width"]), int(item["height"])
    layout = _kind_layout(item["kind"], width, height)
    limit = min(src_w / width, src_h / height, 1.0) if width and height else 1.0
    return {**item, "scale": round(limit, 3), "slots": layout}


def _supersample(canvas: Image.Image, scale: int = 4) -> Image.Image:
    width, height = canvas.size
    return canvas.resize((max(1, width // scale), max(1, height // scale)), Image.Resampling.LANCZOS)


def draw_logo(size: int) -> Image.Image:
    scale = 4
    side = size * scale
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, side - 3, side - 3), fill=GREEN)
    ring = max(8, side // 11)
    draw.ellipse((ring, ring, side - 1 - ring, side - 1 - ring), outline=YELLOW, width=ring)
    glyph = font("display", int(side * 0.36))
    box = draw.textbbox((0, 0), "FC", font=glyph)
    tw, th = box[2] - box[0], box[3] - box[1]
    origin = ((side - tw) / 2 - box[0], (side - th) / 2 - box[1] - side * 0.02)
    draw.text(origin, "FC", font=glyph, fill=YELLOW)
    gap = max(6, side // 28)
    mid = side / 2
    draw.rectangle((side * 0.28, mid - gap / 2, side * 0.72, mid + gap / 2), fill=GREEN)
    return _supersample(image, scale)


def _badge_icon(draw: ImageDraw.ImageDraw, kind: str, box: tuple[int, int, int, int], ink: tuple[int, int, int, int]) -> None:
    x, y, side = box
    if kind == "transfer":
        mid = y + side * 0.5
        draw.polygon([(x, mid - side * 0.12), (x + side * 0.62, y + side * 0.08), (x + side * 0.62, mid - side * 0.12)], fill=ink)
        draw.polygon([(x + side, mid + side * 0.12), (x + side * 0.38, y + side * 0.92), (x + side * 0.38, mid + side * 0.12)], fill=ink)
    elif kind == "insider":
        draw.rounded_rectangle((x, y, x + side, y + side), radius=max(2, side // 5), outline=ink, width=max(3, side // 7))
    elif kind == "urgent":
        draw.rounded_rectangle((x + side * 0.38, y, x + side * 0.62, y + side * 0.62), radius=side * 0.08, fill=ink)
        draw.ellipse((x + side * 0.34, y + side * 0.74, x + side * 0.66, y + side), fill=ink)
    else:
        draw.polygon(
            [
                (x + side * 0.5, y),
                (x + side * 0.62, y + side * 0.36),
                (x + side, y + side * 0.36),
                (x + side * 0.72, y + side * 0.58),
                (x + side * 0.82, y + side),
                (x + side * 0.5, y + side * 0.76),
                (x + side * 0.18, y + side),
                (x + side * 0.28, y + side * 0.58),
                (x, y + side * 0.36),
                (x + side * 0.38, y + side * 0.36),
            ],
            fill=ink,
        )


def badge_width(kind: str, label: str, height: int) -> int:
    icon = int(height * 0.46)
    pad = int(height * 0.28)
    glyph = font("bold", max(12, int(height * 0.42)))
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    text_w = probe.textlength(label, font=glyph)
    return max(height * 3, int(pad + icon + pad + text_w + pad * 1.6))


def draw_badge(kind: str, label: str, width: int, height: int) -> Image.Image:
    scale = 4
    wide, high = width * scale, height * scale
    image = Image.new("RGBA", (wide, high), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    fill = BADGE_FILL.get(kind, YELLOW)
    ink = BADGE_INK.get(kind, BLACK)
    draw.rounded_rectangle((0, 0, wide - 1, high - 1), radius=high // 2, fill=fill)
    icon = int(high * 0.46)
    pad = int(high * 0.28)
    _badge_icon(draw, kind, (pad, (high - icon) // 2, icon), ink)
    glyph = font("bold", int(high * 0.42))
    box = draw.textbbox((0, 0), label, font=glyph)
    tw, th = box[2] - box[0], box[3] - box[1]
    draw.text((pad + icon + pad, (high - th) / 2 - box[1]), label, font=glyph, fill=ink)
    return _supersample(image, scale)


def draw_stripes(width: int, height: int) -> Image.Image:
    scale = 4
    image = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    thick = max(8, int(width * scale * 0.16))
    gap = int(thick * 0.7)
    lean = int(height * scale * 0.45)
    for index in range(3):
        left = index * (thick + gap)
        draw.polygon(
            [(left, 0), (left + thick, 0), (left + thick + lean, height * scale), (left + lean, height * scale)],
            fill=YELLOW,
        )
    return _supersample(image, scale)


def draw_frame(width: int, height: int, radius: int, stroke: int) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((stroke, stroke, width - stroke - 1, height - stroke - 1), radius=radius, outline=YELLOW, width=stroke)
    return image


def _icon(kind: str, size: int, ink: tuple[int, int, int, int]) -> Image.Image:
    scale = 4
    side = size * scale
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = side * 0.16
    if kind == "calendar":
        draw.rounded_rectangle((pad, pad + side * 0.08, side - pad, side - pad), radius=side * 0.08, outline=ink, width=max(4, side // 16))
        draw.line((pad, pad + side * 0.32, side - pad, pad + side * 0.32), fill=ink, width=max(4, side // 16))
    elif kind == "bell":
        draw.pieslice((pad, pad, side - pad, side * 0.78), 200, 340, fill=ink)
        draw.ellipse((side * 0.38, side * 0.72, side * 0.62, side * 0.9), fill=ink)
    elif kind == "send":
        draw.polygon([(pad, side * 0.5), (side - pad, pad), (side * 0.62, side * 0.62), (side - pad * 0.4, side - pad)], fill=ink)
    elif kind == "chart":
        draw.rectangle((pad, side * 0.55, pad + side * 0.16, side - pad), fill=ink)
        draw.rectangle((pad + side * 0.28, side * 0.32, pad + side * 0.44, side - pad), fill=ink)
        draw.rectangle((pad + side * 0.56, side * 0.18, pad + side * 0.72, side - pad), fill=ink)
    elif kind == "crown":
        draw.polygon([(pad, side * 0.72), (pad, side * 0.38), (side * 0.32, side * 0.58), (side * 0.5, pad), (side * 0.68, side * 0.58), (side - pad, side * 0.38), (side - pad, side * 0.72)], fill=ink)
    elif kind == "ball":
        draw.ellipse((pad, pad, side - pad, side - pad), outline=ink, width=max(4, side // 14))
        draw.regular_polygon((side / 2, side / 2, side * 0.16), 5, rotation=270, fill=ink)
    elif kind == "arrows":
        draw.polygon([(pad, side * 0.42), (side * 0.62, pad), (side * 0.62, side * 0.32), (side - pad, side * 0.32), (side - pad, side * 0.52), (side * 0.62, side * 0.52), (side * 0.62, side * 0.68)], fill=ink)
    else:
        draw.ellipse((pad, pad, side - pad, side - pad), outline=ink, width=max(4, side // 12))
    return _supersample(image, scale)


def draw_wordmark(width: int = 1200) -> Image.Image:
    image = Image.new("RGBA", (width, int(width * 0.42)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    bottom = font("display", int(width * 0.2))
    draw.text((0, int(width * 0.12)), "GOL88.RU", font=bottom, fill=YELLOW)
    return image


def draw_chip(label: str, height: int) -> Image.Image:
    glyph = font("bold", max(12, int(height * 0.42)))
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    text_w = int(probe.textlength(label, font=glyph))
    width = text_w + height
    scale = 4
    image = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width * scale - 1, height * scale - 1), radius=height * scale // 2, fill=GREEN)
    big = font("bold", max(12, int(height * scale * 0.42)))
    box = draw.textbbox((0, 0), label, font=big)
    draw.text(((width * scale - (box[2] - box[0])) / 2, (height * scale - (box[3] - box[1])) / 2 - box[1]), label, font=big, fill=YELLOW)
    return _supersample(image, scale)


def _wrap(draw: ImageDraw.ImageDraw, text: str, glyph: ImageFont.ImageFont, width: int) -> list[str]:
    words = re.split(r"\s+", (text or "").strip())
    lines: list[str] = []
    current = ""
    for word in words:
        if not word:
            continue
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=glyph) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit(draw: ImageDraw.ImageDraw, text: str, role: str, max_w: int, max_h: int, lines_limit: int, start: int) -> tuple[ImageFont.ImageFont, list[str], int]:
    size = max(16, start)
    while size >= 15:
        glyph = font(role, size)
        lines = _wrap(draw, text, glyph, max_w)
        line_h = int(size * 1.12)
        fits = lines and len(lines) <= lines_limit and line_h * len(lines) <= max_h
        if fits and all(draw.textlength(line, font=glyph) <= max_w + 1 for line in lines):
            return glyph, lines, line_h
        size -= 2
    glyph = font(role, 15)
    return glyph, _wrap(draw, text, glyph, max_w)[:lines_limit], 17


def cover_photo(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    fitted = ImageOps.fit(source.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.32))
    return fitted.convert("RGBA")


def _panel(canvas: Image.Image, top: int) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rectangle((0, top, canvas.width, canvas.height), fill=(6, 22, 14, 214))
    canvas.alpha_composite(layer)


def _layout_slots(width: int, height: int, template: str, label: str) -> dict:
    margin = max(20, width // 34)
    bar = max(10, width // 70) if template in {"urgent", "scandal"} else 0
    logo_size = max(58, int(min(width, height) * 0.095))
    logo = (margin + bar, height - margin - logo_size, logo_size, logo_size)
    chip_h = max(28, logo_size // 2)
    chip = draw_chip("ФУТБОЛ 24/7", chip_h)
    chip_box = (width - margin - chip.width, logo[1] + (logo_size - chip.height) // 2, chip.width, chip.height)
    footer = (
        logo[0] + logo_size + margin // 2,
        logo[1],
        max(40, chip_box[0] - (logo[0] + logo_size + margin) ),
        logo_size,
    )
    badge_h = max(38, height // 17)
    badge_w = min(int(width * 0.46), badge_width(brand_spec()["templates"][template]["badge"], label, badge_h))
    if template == "meme":
        badge = (width - margin - badge_w, margin, badge_w, badge_h)
    else:
        badge = (margin + bar, margin, badge_w, badge_h)
    text_h = max(96, int(height * 0.30))
    headline_y = max(badge[1] + badge[3] + margin, logo[1] - margin // 2 - text_h)
    headline = (
        margin + bar,
        headline_y,
        width - margin * 2 - bar,
        max(64, logo[1] - margin // 2 - headline_y),
    )
    stripe_w = int(width * 0.11)
    stripe_h = int(height * 0.2)
    if template == "meme":
        stripes = (margin, margin, stripe_w, stripe_h)
    else:
        stripes = (width - margin - stripe_w, margin, stripe_w, stripe_h)
    return {
        "photo": (0, 0, width, height),
        "badge": badge,
        "logo": logo,
        "headline": headline,
        "footer": footer,
        "chip": chip_box,
        "stripes": stripes,
        "bar": bar,
    }


def _draw_lines(draw: ImageDraw.ImageDraw, lines: list[str], glyph: ImageFont.ImageFont, xy: tuple[int, int], line_h: int, fill) -> int:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=glyph, fill=fill)
        y += line_h
    return y


def _paint_body(draw: ImageDraw.ImageDraw, template: str, slots: dict, headline: str, facts: dict) -> None:
    x, y, w, h = slots["headline"]
    summary = (facts.get("summary") or "").strip()
    if template == "quote":
        quote = (facts.get("quote") or headline).strip()
        mark = font("display", max(42, h // 5))
        draw.text((x, y), "«", font=mark, fill=YELLOW)
        shift = int(mark.size * 0.7)
        glyph, lines, line_h = _fit(draw, quote, "display", w - shift, int(h * 0.72), 4, max(28, w // 18))
        cursor = _draw_lines(draw, lines, glyph, (x + shift, y + mark.size // 5), line_h, WHITE)
        author = (facts.get("attribution") or "").strip()
        if author:
            small, who, who_h = _fit(draw, author, "text", w - shift, h // 4, 2, max(16, w // 28))
            _draw_lines(draw, who, small, (x + shift, min(cursor + 8, y + h - who_h * len(who))), who_h, SOFT)
        return
    if template == "result":
        score = (facts.get("score") or "").strip() or "— : —"
        home = (facts.get("home") or "").strip()
        away = (facts.get("away") or "").strip()
        glyph, lines, line_h = _fit(draw, score, "display", w, h // 2, 1, max(48, h // 3))
        score_w = draw.textlength(lines[0], font=glyph) if lines else 0
        _draw_lines(draw, lines, glyph, (x + (w - score_w) / 2, y + h * 0.18), line_h, YELLOW)
        names = ""
        if home and away:
            names = f"{home}    —    {away}"
        else:
            names = home or away
        if names:
            small, rows, row_h = _fit(draw, names, "bold", w, h // 4, 1, max(18, w // 22))
            name_w = draw.textlength(rows[0], font=small)
            _draw_lines(draw, rows, small, (x + (w - name_w) / 2, y + h * 0.62), row_h, WHITE)
        return
    if template == "fixture":
        home = (facts.get("home") or "ХОЗЯЕВА").strip()
        away = (facts.get("away") or "ГОСТИ").strip()
        kick = (facts.get("kickoff") or "").strip()
        line = f"{home}    vs    {away}"
        glyph, lines, line_h = _fit(draw, line, "display", w, h // 2, 2, max(28, w // 16))
        cursor = y + h * 0.2
        cursor = _draw_lines(draw, lines, glyph, (x, cursor), line_h, WHITE)
        if kick:
            small, rows, row_h = _fit(draw, kick, "display", w, h // 4, 1, max(22, w // 14))
            _draw_lines(draw, rows, small, (x, cursor + 6), row_h, YELLOW)
        venue = (facts.get("venue") or "").strip()
        if venue:
            tiny, rows, row_h = _fit(draw, venue, "text", w, h // 5, 1, max(16, w // 28))
            _draw_lines(draw, rows, tiny, (x, y + h - row_h - 4), row_h, SOFT)
        return
    if template == "stats":
        value = (facts.get("stat_value") or "").strip() or "—"
        label = (facts.get("stat_label") or summary).strip()
        glyph, lines, line_h = _fit(draw, value, "display", w, int(h * 0.62), 1, max(56, h // 2))
        cursor = _draw_lines(draw, lines, glyph, (x, y), line_h, YELLOW)
        if label:
            small, rows, row_h = _fit(draw, label, "bold", w, h // 3, 2, max(18, w // 24))
            _draw_lines(draw, rows, small, (x, cursor + 4), row_h, WHITE)
        return
    title_budget = int(h * 0.5)
    glyph, lines, line_h = _fit(draw, headline, "display", w, title_budget, 3, max(26, w // 16))
    extra = ""
    extra_fill = SOFT
    extra_role = "text"
    if template == "transfer" and facts.get("amount"):
        extra = f"Сумма трансфера: {facts['amount']}"
        extra_fill = YELLOW
        extra_role = "bold"
    elif summary and summary != headline:
        extra = summary
    extra_lines: list[str] = []
    extra_font = glyph
    extra_line = 0
    if extra:
        extra_font, extra_lines, extra_line = _fit(draw, extra, extra_role, w, max(24, h // 3), 2, max(16, w // 28))
    block = line_h * max(1, len(lines)) + (extra_line * len(extra_lines) + 8 if extra_lines else 0)
    cursor = y + max(0, h - block)
    cursor = _draw_lines(draw, lines, glyph, (x, cursor), line_h, WHITE)
    if extra_lines:
        _draw_lines(draw, extra_lines, extra_font, (x, cursor + 8), extra_line, extra_fill)
    if template == "scandal":
        draw.rectangle((x, y + h - 6, x + min(w, 220), y + h - 2), fill=RED)


def compose(source: Image.Image, *, template: str, headline: str, footer: str, facts: dict | None = None) -> tuple[Image.Image, dict]:
    facts = dict(facts or {})
    spec = brand_spec()["templates"][template]
    label = (facts.get("competition") or spec["label"]) if template in {"result", "fixture"} else spec["label"]
    chosen = choose_size(source.width, source.height, "square")
    width, height = chosen["width"], chosen["height"]
    slots = _layout_slots(width, height, template, label)
    slots["photo"] = tuple(chosen["slots"]["photo"])
    canvas = Image.new("RGBA", (width, height), PANEL)
    px, py, pw, ph = slots["photo"]
    canvas.alpha_composite(cover_photo(source, (pw, ph)), (px, py))
    if template in {"result", "fixture", "stats", "quote"}:
        _panel(canvas, int(height * 0.28))
    elif template in PHOTO_LED or template == "scandal":
        _panel(canvas, max(0, slots["headline"][1] - 16))
    if slots["bar"]:
        bar = Image.new("RGBA", (slots["bar"], height), RED)
        canvas.alpha_composite(bar, (0, 0))
    elements = ["frame", "logo", "badge", "chip-247", "footer"]
    if template in STRIPED and not boxes_overlap(slots["stripes"], slots["badge"]) and not boxes_overlap(slots["stripes"], slots["headline"]):
        stripes = draw_stripes(slots["stripes"][2], slots["stripes"][3])
        canvas.alpha_composite(stripes, (slots["stripes"][0], slots["stripes"][1]))
        elements.append("stripes")
    else:
        slots.pop("stripes", None)
    badge = draw_badge(spec["badge"], label, slots["badge"][2], slots["badge"][3])
    canvas.alpha_composite(badge, (slots["badge"][0], slots["badge"][1]))
    text_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    _paint_body(text_draw, template, slots, headline, facts)
    foot = (footer or "").strip()
    if foot:
        fx, fy, fw, fh = slots["footer"]
        glyph, lines, line_h = _fit(text_draw, foot, "bold", fw, fh, 2, max(15, fh // 3))
        _draw_lines(text_draw, lines[:2], glyph, (fx, fy + max(0, (fh - line_h * len(lines[:2])) // 2)), line_h, YELLOW)
    canvas.alpha_composite(text_layer)
    logo = draw_logo(slots["logo"][2])
    canvas.alpha_composite(logo, (slots["logo"][0], slots["logo"][1]))
    chip = draw_chip("ФУТБОЛ 24/7", slots["chip"][3])
    canvas.alpha_composite(chip, (slots["chip"][0], slots["chip"][1]))
    frame = draw_frame(width, height, max(12, width // 48), max(4, width // 180))
    canvas.alpha_composite(frame)
    elements.append(template)
    meta = {
        "template": template,
        "badge": spec["badge"],
        "label": label,
        "elements": elements,
        "size_id": chosen["id"],
        "width": width,
        "height": height,
        "scale": chosen["scale"],
        "slots": {key: [int(v) for v in value] for key, value in slots.items() if key != "bar"},
        "headline": headline,
    }
    return canvas.convert("RGB"), meta


def _plate(logo: Image.Image, fill: tuple[int, int, int, int]) -> Image.Image:
    pad = logo.width // 8
    side = logo.width + pad * 2
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, side - 1, side - 1), radius=side // 8, fill=fill)
    image.alpha_composite(logo, (pad, pad))
    return image


def _series(kind: str, label: str) -> Image.Image:
    image = Image.new("RGBA", (640, 760), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((70, 40, 570, 540), fill=(12, 28, 18, 255), outline=YELLOW, width=10)
    icon = _icon(kind, 280, WHITE).resize((280, 280), Image.Resampling.LANCZOS)
    image.alpha_composite(icon, (180, 150))
    glyph = font("bold", 54)
    box = draw.textbbox((0, 0), label, font=glyph)
    draw.text(((640 - (box[2] - box[0])) / 2, 590), label, font=glyph, fill=WHITE)
    return image


def save_element_kit(target: Path) -> list[str]:
    target.mkdir(parents=True, exist_ok=True)
    logo = draw_logo(1024)
    pieces: dict[str, Image.Image] = {
        "logo.png": logo,
        "logo-on-dark.png": _plate(logo.resize((768, 768), Image.Resampling.LANCZOS), GREEN),
        "logo-on-light.png": _plate(logo.resize((768, 768), Image.Resampling.LANCZOS), LIGHT),
        "wordmark.png": draw_wordmark(1400),
        "stripes.png": draw_stripes(720, 420),
        "frame.png": draw_frame(1280, 720, 28, 14),
        "chip-247.png": draw_chip("ФУТБОЛ 24/7", 160),
    }
    for key, item in brand_spec()["templates"].items():
        height = 280
        width = badge_width(item["badge"], item["label"], height)
        pieces[f"badge-{key}.png"] = draw_badge(item["badge"], item["label"], width, height)
    icons = {
        "calendar": "calendar",
        "bell": "bell",
        "send": "send",
        "chart": "chart",
        "crown": "crown",
        "ball": "ball",
        "arrows": "arrows",
    }
    for name, kind in icons.items():
        pieces[f"icon-{name}.png"] = _icon(kind, 512, YELLOW)
    plaques = {
        "news": ("calendar", "НОВОСТИ"),
        "transfers": ("arrows", "ТРАНСФЕРЫ"),
        "insider": ("chart", "ИНСАЙДЫ"),
        "analytics": ("chart", "АНАЛИТИКА"),
    }
    for name, (icon, label) in plaques.items():
        row = Image.new("RGBA", (1100, 220), (0, 0, 0, 0))
        draw = ImageDraw.Draw(row)
        draw.rounded_rectangle((0, 0, 1099, 219), radius=36, fill=(10, 32, 20, 255))
        mark = _icon(icon, 120, YELLOW)
        row.alpha_composite(mark, (36, 50))
        glyph = font("bold", 64)
        box = draw.textbbox((0, 0), label, font=glyph)
        draw.text((190, (220 - (box[3] - box[1])) / 2 - box[1]), label, font=glyph, fill=WHITE)
        pieces[f"plaque-{name}.png"] = row
    series = {
        "transfer": ("arrows", "Трансферы"),
        "insider": ("send", "Инсайды"),
        "analytics": ("chart", "Аналитика"),
        "result": ("ball", "Результаты"),
        "interview": ("bell", "Интервью"),
        "meme": ("crown", "Мемы"),
    }
    for name, (kind, label) in series.items():
        pieces[f"series-{name}.png"] = _series(kind, label)
    written = []
    for name, image in pieces.items():
        image.save(target / name)
        written.append(name)
    return written


def slice_storyboard(storyboard: Path, target: Path) -> None:
    """Нарезка макета как карта зон, не как боевые файлы."""
    target.mkdir(parents=True, exist_ok=True)
    image = Image.open(storyboard).convert("RGB")
    width, height = image.size
    bands = {
        "header": (0, 0, width, int(height * 0.18)),
        "kit-row": (0, int(height * 0.17), width, int(height * 0.34)),
        "templates": (0, int(height * 0.32), width, int(height * 0.60)),
        "plaques": (0, int(height * 0.58), width, int(height * 0.82)),
        "feed": (0, int(height * 0.78), width, height),
    }
    for name, box in bands.items():
        image.crop(box).save(target / f"{name}.jpg", quality=90)
