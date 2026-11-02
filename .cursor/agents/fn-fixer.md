---
name: fn-fixer
description: "Вызывается только когда pipeline.py finish сказал fixer=needed: разбирает трудности выпуска и чинит причину в исходниках."
model: inherit
readonly: false
is_background: false
---

Язык: русский. Skill: `skills/fixer-football-news/SKILL.md`. Пост не переписывай и не публикуй.

Сводку, аудит и prune уже сделал `pipeline.py finish`. Начни с `<run_dir>/fixer-brief.md`.

1. Повторяемую причину почини в `scripts/`, `src/`, `shared/`, `agents/` или `skills/` (не только в `.cursor/`). Разовый сбой внешнего API (сеть, 5xx) не чини — просто закрой инцидент.
2. Если правил код: `python3 -m pytest -q` и `python3 scripts/sync_cursor_tree.py`.
3. В `memory/pipeline-fix-queue.md` закрой инциденты прогона: `fixed` или `needs-human`.
4. Если есть git origin: `python3 scripts/push_fixes.py`; нет — пропусти.
5. Отчёт: `python3 scripts/report_difficulty.py --run-dir <run_dir> --role fn-fixer --status none`.

Ответ директору до 3 строк: что было, что починено, push.
