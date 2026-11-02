# Cloud runbook

Репозиторий: **https://github.com/fansmok/tgnews** (ветка `main` для Automation).

Репозиторий клонируется в чистую Ubuntu VM. Зависимости ставит `.cursor/environment.json`. Секреты VM берёт из Cursor Dashboard, не из git.

Первый запуск делайте вручную и с `PUBLISH_ALLOW=no`. Когда сухой прогон доходит до `publish-result.json` со статусом `dry_run`, переключайте секрет на `yes`.

Расписание для боевого режима: каждые 15 минут с 09:00 до 23:59 МСК. В UTC это `*/15 6-20 * * *`. Холостой запуск (слот ещё рано) — один вызов `pipeline.py gate` без агентов.

Дешевле всего гонять `scripts/cron_gate.sh` (обёртка над `pipeline.py gate`) по cron и открывать Cursor только когда `status=ready`.

### Cron на Mac (локально)

Репозиторий и `.env` должны быть на машине, которая крутит cron (сеть, `ADS_CHANNEL`, ключи Gemini/Kie для полного выпуска позже).

```bash
crontab -e
```

Каждые 15 минут, 09:00–23:59 **по Москве** (на Mac задай TZ в crontab):

```cron
CRON_TZ=Europe/Moscow
*/15 9-23 * * * /Users/fansmok/Desktop/NEWS-AGENT/scripts/cron_gate.sh
```

Лог: `memory/cron-gate.log`. Код выхода: `0` = слот готов, `2` = рано (idle), `1` = ошибка.

Уведомление на Mac, когда слот открылся (добавь в crontab или в `~/.zshrc` перед cron):

```bash
export NEWS_AGENT_NOTIFY_CMD='osascript -e "display notification \"Слот готов — открой Agent\" with title \"NEWS-AGENT\""'
```

### VPS (Linux)

Тот же cron, путь к проекту и `python3` из venv:

```cron
CRON_TZ=Europe/Moscow
*/15 9-23 * * * cd /path/to/NEWS-AGENT && ./scripts/cron_gate.sh
```

На сервере нужны те же секреты, что локально (`.env` или переменные окружения). Рекламу можно подхватывать через `watch_ads.py` / `webhook_ads.py` отдельно.

**Важно:** `gate` только проверяет «пора ли готовить пост». Текст, критик и публикацию всё равно делает Agent в **новом чате** (~250k токенов) или отдельная автоматизация Cursor Cloud.

## Полностью в Cursor Cloud (без Mac и без своего cron)

Идея: репозиторий + секреты в [Cloud Agents](https://cursor.com/dashboard/cloud-agents), расписание — **Cursor Automation**, один прогон = облачная VM + агент по `agents/fn-director.md`. Публикация в Telegram идёт **с этой VM** (`publish.py`), не с вашего ноутбука.

### Что где крутится

| Часть | Где |
|-------|-----|
| `gate` / `scout` / `produce` / `publish` / `finish` | Ubuntu VM Cloud Agent (`scripts/pipeline.py`) |
| Gemini, Kie, Telegram API | Запросы с VM по секретам Dashboard |
| **fn-critic**, fn-copy, fn-fixer | Subagent Task внутри того же Cloud Agent (токены **Included / Cloud Agents** в биллинге Cursor) |
| Расписание «каждые 15 мин 09–23 МСК» | Automation → trigger **On a schedule** (cron) |
| Установка deps | `.cursor/environment.json` → `install` + `doctor.py` |

Локальный Mac, `cron_gate.sh` и ручное открытие Cursor **не обязательны**, если Automation запускает агента по расписанию.

### Подготовка (один раз)

1. **Репозиторий** на GitHub или Origin, подключён к Cursor (ветка `main` / ваша рабочая).
2. **Dashboard → Cloud Agents → Secrets** — те же переменные, что в `.env.example` (`TELEGRAM_*`, `ADS_CHANNEL`, `GEMINI_*`, `KIE_*`, `PUBLISH_ALLOW`, `PUBLISH_BACKEND`, …). Секреты в git не класть.
3. **Первый прогон вручную** из Dashboard или Automation с `PUBLISH_ALLOW=no` — до `publish-result.json` со статусом `dry_run`. Потом `PUBLISH_ALLOW=yes`.
4. **Custom emoji / Premium** — если нужны гербы в посте: `PUBLISH_BACKEND=user` и `TELEGRAM_STRING_SESSION` в секретах; один раз локально `login_user.py`, строку сессии — в секреты.

### Automation (расписание)

В Cursor: **Automations** → новая автomation:

- **Trigger:** расписание, cron каждые 15 минут в окне выпусков. В UTC для 09:00–23:59 МСК (UTC+3): `*/15 6-20 * * *`. Если редактор поддерживает только «локальное» время — задайте эквivalent 9–23 по Москве так, как показывает UI.
- **Repo / branch:** этот репозиторий, ветка с актуальным `agents/` и `scripts/`.
- **Cloud compute:** включено в [Cloud Agent dashboard](https://cursor.com/dashboard/cloud-agents) для аккаунта/команды.
- **Instructions (промпт):**

```text
Выпуск футбольной новости по agents/fn-director.md. Начни с python3 scripts/pipeline.py gate; если idle — сразу закончи одной строкой с next_publish_at. Иначе scout → produce → fn-critic → publish → finish; fn-copy и fn-fixer только по сигналу pipeline.
```

Агент сам вызывает subagent **fn-critic** (обязательно для publish). Director не пишет текст и не подменяет критика.

### Реклама и слоты

На каждом `gate` скрипт читает канал рекламы (нужны `ADS_CHANNEL` и доступ Telethon при закрытом канале). Отдельный `watch_ads.py` на VPS **не обязателен**, если Automation достаточно часто дергает `gate`. Мгновенный пересчёт сразу после поста в рекламе — опционально: свой маленький VPS с `webhook_ads.py` или редкий polling; Cloud Agent webhook для Telegram сам по себе не заменяет Telegram Bot API webhook без публичного URL.

### Токены и «холостые» прогоны

| Схема | Cursor-токены на «слот рано» |
|-------|------------------------------|
| `cron_gate.sh` на VPS/Mac | **0** (только Python) |
| Automation каждые 15 мин | **есть**: стартует Cloud Agent, даже если после `gate` одна строка и выход |

Экономия на idle — внешний cron только `gate` + Automation **по webhook** или реже; полный cloud без своего сервера — удобство в обмен на ~десятки коротких agent-run в день.

### Что Automation не заменяет

- Смысл **fn-critic** — без LLM publish не пройдёт (так задумано в `AGENTS.md`).
- Gemini/Kie — отдельные ключи и квоты провайдеров, не путать с лимитом Composer в Cursor.
