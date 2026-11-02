---
name: fixer-football-news
description: Разбор трудностей футбольного выпуска и долговечная починка причины. Использовать роли fn-fixer, только когда pipeline.py finish вернул fixer=needed.
disable-model-invocation: true
---

# Fixer

Контракт отчёта: `shared/pipeline-incident-fix-contract.md`.

- `difficulties/<role>.json` со `status: difficulty` уже лежит в `memory/pipeline-fix-queue.md`. Секретов там нет; если увидел токен — не копируй, пометь `needs-human`.
- Чини причину, а не симптом, и не ухудшай качество текста, фото и проверок. Перед правкой поищи готовое решение в коде.
- Экономия токенов: если видишь лишний шаг, повтор или раздутый промпт — убери его, но только если проверки и качество поста не страдают. Мысли, которые не сделал сейчас, — одной строкой в `memory/optimization-notes.md`.
- Push только через `scripts/push_fixes.py` (он сам исключает `.env`, базу, сессию и handoff). Нет origin — статус `skipped`, выпуск не переигрывать.
