"""Порог пересборки карточки Kie. Мелочи не тратят новую генерацию."""

from __future__ import annotations

# Только эти формулировки имеют право заново звать Kie.
# Обычный кадр, кривая кисть или плашка GOL88.RU сюда не входят.
EXTREME_MARKERS = (
    "не футбол",
    "другой вид спорта",
    "не тот вид спорта",
    "пустая картин",
    "пустое фото",
    "нет изображен",
    "нечитаем",
    "сплошной цвет",
    "чужой логотип",
    "логотип сми",
    "логотип медиа",
    "водяной знак сми",
    "нет головы",
    "без головы",
    "лишние конеч",
    "слипшиеся тел",
)


def _mentions_house_mark(text: str) -> bool:
    compact = text.replace(" ", "").replace(".", "")
    return "gol88" in compact or "гол88" in compact


def extreme_design_issues(issues: list[str]) -> list[str]:
    """Оставляет только брак, из-за которого карточку нельзя публиковать."""
    kept: list[str] = []
    for issue in issues:
        low = issue.casefold()
        extreme = any(marker in low for marker in EXTREME_MARKERS)
        if _mentions_house_mark(low) and not extreme:
            continue
        if extreme:
            kept.append(issue)
    return kept
