from __future__ import annotations

TOPICS = {
    "result": ("⚽️", "🏆"),
    "fixture": ("📅", "🆚"),
    "transfer": ("✍️", "💰"),
    "injury": ("🚑", None),
    "sack": ("🚨", None),
    "urgent": ("⚡️", None),
    "quote": ("🎙", None),
    "stats": ("📊", None),
    "scandal": ("⚠️", None),
    "insider": ("🤫", None),
    "meme": ("😄", None),
    "main": ("📰", None),
}


def _topic(template: str, story: dict, copy: dict) -> str:
    action = (story or {}).get("action") or ""
    if template == "urgent" and action == "injury":
        return "injury"
    if template == "urgent" and action == "sack":
        return "sack"
    if template in TOPICS:
        return template
    return "main"


def _override(text: str, topic: str) -> str:
    lowered = text.lower()
    if "золот" in lowered or "ballond" in lowered or "ballon" in lowered:
        return "quote" if topic == "quote" else "stats"
    return topic


def pick_standard(story: dict, copy: dict, template: str) -> dict:
    blob = " ".join(
        part
        for part in (
            (copy or {}).get("title") or "",
            " ".join((copy or {}).get("paragraphs") or []),
            (story or {}).get("title") or "",
        )
        if part
    )
    topic = _override(blob, _topic(template, story, copy))
    if "золот" in blob.lower():
        title, paragraph = "🏆", None
        topic = "trophy"
    else:
        title, paragraph = TOPICS[topic if topic in TOPICS else "main"]
    paragraphs = [part for part in (copy or {}).get("paragraphs") or [] if part and part.strip()]
    paragraph_emoji = []
    for index, _paragraph in enumerate(paragraphs):
        if index == 0 and paragraph and paragraph != title:
            paragraph_emoji.append({"fallback": paragraph, "tags": [topic], "mode": "standard"})
        else:
            paragraph_emoji.append(None)
    return {
        "title_emoji": {"fallback": title, "tags": [topic], "mode": "standard"},
        "paragraph_emoji": paragraph_emoji,
    }
