from __future__ import annotations

import re

NAV_MARKERS = (
    "главная",
    "меню",
    "навигац",
    "матч-центр",
    "трансфер",
    "видео",
    "таблиц",
    "календар",
    "подписаться",
    "войти",
    "поиск",
    "хоккей",
    "баскетбол",
    "теннис",
    "читайте также",
    "все новости",
)

MENU_FACT_RULE = (
    "Если текст страницы похож на меню сайта — короткие пункты разделов, чужие заголовки, "
    "«читайте также», — не добавляй факты вне заголовка и summary карточки. "
    "Минуту, счёт, цитату и имена бери только из title и summary."
)

BOLD_SPAN_RULE = (
    "bold_spans — точные подстроки абзацев. "
    "Если абзаца нет, bold_spans оставь пустым. "
    "Если абзац есть, сначала счёт, сумма, минута, отрыв в очках или срок, и только если эта цифра есть в title или summary. "
    "Если такой цифры в абзаце нет, положи в bold_spans ключевое имя человека из абзаца "
    "(игрок или тренер): уже написанную подстроку, без кавычек клуба. Имя не выдумывай. "
    "Если нет и имени, выдели короткую оговорку из абзаца, которой нет в заголовке."
)

_EMOJI = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F"
    "\u200D"
    "]+"
)


def looks_like_menu(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 8:
        return False
    short = sum(1 for line in lines if len(line) <= 40)
    if short / len(lines) < 0.6:
        return False
    lowered = text.lower().replace("ё", "е")
    hits = sum(1 for marker in NAV_MARKERS if marker in lowered)
    return hits >= 3


def source_for_copy(title: str, summary: str, page: str) -> tuple[str, bool]:
    menu = looks_like_menu(page)
    parts = [part.strip() for part in (title, summary, "" if menu else page) if part and part.strip()]
    return "\n".join(parts), menu


def strip_emoji(text: str) -> str:
    cleaned = _EMOJI.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def _unwrap_quote(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) >= 2 and cleaned[0] in "«\"“" and cleaned[-1] in "»\"”":
        return cleaned[1:-1].strip()
    return cleaned


def _flat(text: str) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", " ", text.lower().replace("ё", "е")).strip()


_META = {
    "высказал",
    "высказался",
    "поделился",
    "рассказал",
    "заявил",
    "сказал",
    "отметил",
    "прокомментировал",
    "вспомнил",
    "воспоминание",
    "воспоминаниями",
    "период",
    "периоде",
    "выступление",
    "выступлений",
    "игра",
    "игре",
    "игрой",
    "комментарий",
    "интервью",
}


def _tokens(text: str) -> set[str]:
    stop = {"и", "в", "во", "на", "с", "к", "о", "об", "от", "для", "по", "из", "за", "что", "это", "как", "уже", "его", "ее", "не"}
    return {token for token in _flat(text).split() if token not in stop and len(token) > 2}


def _clubs(text: str) -> set[str]:
    return {_flat(item) for item in re.findall(r"«([^»]+)»", text)}


def _names(text: str) -> set[str]:
    return {word.lower().replace("ё", "е") for word in re.findall(r"[А-ЯЁ][а-яё]+", text)}


def keep_summary_fact(title: str, paragraphs: list[str], summary: str) -> list[str]:
    """Факт из summary, которого нет в заголовке, остаётся абзацем."""
    if any(part.strip() for part in paragraphs):
        return paragraphs
    fact = summary.strip()
    if not fact or restates_title(title, fact):
        return [part for part in paragraphs if part.strip()]
    if len(fact) > 320:
        fact = fact[:320].rsplit(" ", 1)[0].strip()
    return [fact]


def person_span(body: str) -> str:
    clubs = {item.lower().replace("ё", "е") for item in re.findall(r"«([^»]+)»", body)}
    for match in re.finditer(r"[А-ЯЁ][а-яё]{3,}", body):
        if match.start() == 0:
            continue
        if body[match.start() - 1] in ".!?\n":
            continue
        word = match.group(0)
        if word.lower().replace("ё", "е") in clubs:
            continue
        return word
    return ""


def clause_outside_title(title: str, body: str) -> str:
    parts = re.split(r"[,;]", body)
    if len(parts) < 2:
        return ""
    tail = parts[-1].strip().rstrip(".").strip()
    if not (4 <= len(tail) <= 80):
        return ""
    folded = tail.lower().replace("ё", "е")
    if folded in title.lower().replace("ё", "е"):
        return ""
    if tail not in body:
        return ""
    return tail


def restates_title(title: str, paragraph: str) -> bool:
    """Абзац не нужен, если он только говорит то же, что заголовок."""
    title_flat = _flat(title)
    para_flat = _flat(paragraph)
    if not title_flat or not para_flat:
        return False
    if para_flat == title_flat or para_flat in title_flat or title_flat in para_flat:
        return True
    if set(re.findall(r"\d+", paragraph)) - set(re.findall(r"\d+", title)):
        return False
    if _clubs(paragraph) - _clubs(title):
        return False
    if _names(paragraph) - _names(title):
        return False
    title_tokens = _tokens(title)
    para_tokens = _tokens(paragraph)
    if not para_tokens or not title_tokens:
        return False
    fresh = para_tokens - title_tokens
    return not fresh or fresh <= _META


def _without_quote(text: str, quote: str) -> str:
    cleaned = text
    for piece in (f"«{quote}»", f"\"{quote}\"", f"“{quote}”", quote):
        cleaned = cleaned.replace(piece, " ")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" \t:—-–")


def detach_quote(title: str, paragraphs: list[str], quote_text: str) -> tuple[str, list[str], str]:
    """Цитата живёт только в блоке цитаты. Заголовок и абзац её не повторяют."""
    quote = _unwrap_quote(quote_text)
    original_title = title.strip()
    if quote:
        title = _without_quote(original_title, quote)
        if len(title) < 8:
            title = _without_quote(original_title.split(":")[0], quote) or original_title
    kept: list[str] = []
    for part in paragraphs:
        cleaned = _without_quote(part, quote) if quote else part.strip()
        flat = _flat(cleaned)
        if not flat or restates_title(title, cleaned):
            continue
        kept.append(cleaned)
    body_flat = _flat(title + " " + " ".join(kept))
    if quote and _flat(quote) in body_flat:
        quote = ""
    return title.strip(), kept, quote


def repeats_quote(title: str, paragraphs: list[str], quote_text: str) -> bool:
    quote = _flat(quote_text)
    if len(quote) < 12:
        return False
    return quote in _flat(title + " " + " ".join(paragraphs))
