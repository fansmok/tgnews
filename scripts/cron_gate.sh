#!/usr/bin/env bash
# Проверка слота без Cursor (0 токенов).
# exit 0 + JSON status=ready  → можно запускать выпуск (новый чат Agent / director).
# exit 2 + status=idle        → слот рано, ничего не делать.
# exit 1                      → ошибка (смотри лог).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${NEWS_AGENT_GATE_LOG:-$ROOT/memory/cron-gate.log}"
PYTHON="${NEWS_AGENT_PYTHON:-python3}"
NOTIFY="${NEWS_AGENT_NOTIFY_CMD:-}"

mkdir -p "$(dirname "$LOG")"
cd "$ROOT"

stamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
line="$("$PYTHON" scripts/pipeline.py gate 2>&1 | tail -1)" || true
code=$?

{
  echo "[$stamp] exit=$code $line"
} >>"$LOG"

if [[ $code -eq 0 ]] && [[ -n "$NOTIFY" ]]; then
  # Пример: export NEWS_AGENT_NOTIFY_CMD='osascript -e "display notification \"Слот готов\" with title \"NEWS-AGENT\""'
  eval "$NOTIFY"
fi

exit "$code"
