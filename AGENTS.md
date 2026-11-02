# Football News Cloud Instructions

Язык работы: русский.

Механику выпуска делает `scripts/pipeline.py` (скрипты, без модели). Модель тратится только там, где нужен смысл:

```text
pipeline.py gate      → idle: выход сразу, агентов не запускать
pipeline.py scout     → no_news / slot_busy: сразу finish
pipeline.py produce   → текст Gemini + emoji + голос ‖ фото + карточка Kie/fallback + ревью
   код 3 → Task fn-copy (Gemini недоступен) → pipeline.py after_copy
Task fn-critic        → PASS | REWORK (до 2 раз: pipeline.py rework --target …)
pipeline.py publish
pipeline.py finish    → fixer=needed: Task fn-fixer; fixer=skip: конец
```

Роли-агенты: `fn-director`, `fn-critic` (каждый выпуск), `fn-copy` (только если Gemini упал), `fn-fixer` (только при трудностях). Порядок и gates: `agents/fn-director.md`.

## Что считать ошибкой

- Director сам написал текст поста или сам вынес вердикт критика.
- Публикация без `critic.json` PASS и машинного PASS (`publish` проверяет сам).
- Сообщение ушло во время рекламной паузы или перебитие не на точную минуту `publish_at`.
- Опубликована новость, которая уже есть в `memory/news.db`.
- `finish` сказал `fixer=needed`, а `fn-fixer` не запущен.
- В git попал секрет или отчёт о трудности с токеном.

## Пути

`agents/` и `skills/` — исходники, `.cursor/agents|skills/` — копии (после правки: `python3 scripts/sync_cursor_tree.py`). Контракты — `shared/`, скрипты — `scripts/`, память — `memory/`, инциденты — `memory/pipeline-fix-queue.md`.

## Секреты

Только Cursor Dashboard Secrets или локальный `.env`: `TELEGRAM_BOT_TOKEN`, `NEWS_CHANNEL_ID`, `ADS_CHANNEL`, `PUBLISH_ALLOW` (yes/no), `PUBLISH_BACKEND` (bot/user), `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_STRING_SESSION`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `KIE_API_KEY`, `KIE_MODEL`. В отчёты и handoff не писать.

## Правила контента и сетки (подробно — в `shared/`)

- Текст — близкий перевод (`shared/editorial-policy.md`), комментарий — отдельно (`shared/voice.md`). Оба пишет Gemini.
- 2 клуба в новости → 2 герба в начале заголовка.
- Новость ищется за весь день (до 30 кандидатов), берётся лучшая неопубликованная.
- 6 постов в день в плавающих окнах; обычная реклама: пауза 1 ч, затем посты +1ч и +1ч30м; «трансляция»: пауза 15 мин, затем +15м, +45м, +1ч30м (`shared/schedule-policy.md`).
- Новое сообщение в канале рекламы → `scripts/webhook_ads.py` / `scripts/watch_ads.py` пересчитывает слоты.

## Отчёты о трудностях

Этапы `pipeline.py` сдают отчёты ролей сами. Агент-роль перед выходом:

```bash
python3 scripts/report_difficulty.py --run-dir <run_dir> --role <role> --status none
```

При сбое — `--status difficulty --severity … --summary … --recovered … --fix … --files …`.
