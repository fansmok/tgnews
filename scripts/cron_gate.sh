#!/usr/bin/env bash
# Проверка слота без Cursor (0 токенов).
# exit 0 + JSON status=ready  → один раз зовём webhook/уведомление, дальше выпуск делает Agent.
# exit 2 + status=idle        → слот рано, ничего не делать.
# exit 1                      → ошибка gate (смотри лог).
# Повтор того же publish_at webhook не шлёт: слот остаётся ready десятки минут.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${NEWS_AGENT_GATE_LOG:-$ROOT/memory/cron-gate.log}"
STATE="${NEWS_AGENT_GATE_STATE:-$ROOT/memory/cron-gate.state}"
PYTHON="${NEWS_AGENT_PYTHON:-python3}"
NOTIFY="${NEWS_AGENT_NOTIFY_CMD:-}"

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")"
cd "$ROOT"

# .env читает сам pipeline.py. Здесь нужны только переменные сигнала.
if [[ -f "$ROOT/.env" ]]; then
  eval "$(python3 - "$ROOT/.env" <<'PY'
import shlex, sys
from pathlib import Path
wanted = {
    "CURSOR_AUTOMATION_WEBHOOK_URL",
    "CURSOR_AUTOMATION_WEBHOOK_TOKEN",
    "NEWS_AGENT_NOTIFY_CMD",
}
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    raw = line.strip()
    if not raw or raw.startswith("#") or "=" not in raw:
        continue
    key, value = raw.split("=", 1)
    key = key.strip()
    if key not in wanted:
        continue
    value = value.strip().strip("\"'")
    if not key.replace("_", "").isalnum():
        continue
    print(f"export {key}={shlex.quote(value)}")
PY
)"
  NOTIFY="${NEWS_AGENT_NOTIFY_CMD:-$NOTIFY}"
fi

WEBHOOK_URL="${CURSOR_AUTOMATION_WEBHOOK_URL:-}"
WEBHOOK_TOKEN="${CURSOR_AUTOMATION_WEBHOOK_TOKEN:-}"

stamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
# set -e вместе с «|| true» затирает код gate. Код нужен: 0 ready, 2 idle, 1 ошибка.
set +e
line="$("$PYTHON" scripts/pipeline.py gate 2>&1 | tail -1)"
code=$?
set -e

publish_at=""
if [[ $code -eq 0 ]]; then
  publish_at="$(printf '%s' "$line" | python3 -c 'import json,sys
try:
    print(json.loads(sys.stdin.read()).get("publish_at") or "")
except Exception:
    print("")')"
fi

signaled="no"
if [[ $code -eq 0 && -n "$publish_at" && -f "$STATE" && "$(cat "$STATE")" == "$publish_at" ]]; then
  signaled="skip"
elif [[ $code -eq 0 && -n "$publish_at" ]]; then
  delivered=0
  if [[ -n "$NOTIFY" ]]; then
    eval "$NOTIFY" || echo "[$stamp] notify_failed" >>"$LOG"
  fi
  if [[ -n "$WEBHOOK_URL" && -n "$WEBHOOK_TOKEN" ]]; then
    set +e
    printf '%s' "$line" | CURSOR_AUTOMATION_WEBHOOK_URL="$WEBHOOK_URL" CURSOR_AUTOMATION_WEBHOOK_TOKEN="$WEBHOOK_TOKEN" python3 -c '
import os, sys, urllib.request
req = urllib.request.Request(
    os.environ["CURSOR_AUTOMATION_WEBHOOK_URL"],
    data=sys.stdin.buffer.read(),
    method="POST",
    headers={
        "Authorization": "Bearer " + os.environ["CURSOR_AUTOMATION_WEBHOOK_TOKEN"],
        "Content-Type": "application/json",
    },
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status < 200 or resp.status >= 300:
            raise SystemExit(1)
except Exception:
    raise SystemExit(1)
'
    hook=$?
    set -e
    if [[ $hook -eq 0 ]]; then
      delivered=1
      echo "[$stamp] webhook_ok" >>"$LOG"
    else
      echo "[$stamp] webhook_failed" >>"$LOG"
    fi
  elif [[ -n "$NOTIFY" ]]; then
    delivered=1
  fi
  if [[ $delivered -eq 1 ]]; then
    printf '%s' "$publish_at" >"$STATE"
    signaled="yes"
  fi
fi

{
  echo "[$stamp] exit=$code signaled=$signaled $line"
} >>"$LOG"

exit "$code"
