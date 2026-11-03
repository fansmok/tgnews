#!/usr/bin/env bash
# Mechanical part of one batch slot: open → scout → produce. Prints run_dir on success.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PUBLISH_AT="$1"
REASON="$2"
open_out=$(python3 scripts/open_post.py --publish-at "$PUBLISH_AT" --reason "$REASON")
run_dir=$(echo "$open_out" | awk -F= '/^run_dir=/{print $2}')
scout=$(python3 scripts/pipeline.py scout --run-dir "$run_dir" 2>&1 | tail -1)
if echo "$scout" | grep -q '"status": "no_news"'; then
  echo "SKIP no_news $run_dir"
  exit 2
fi
produce=$(python3 scripts/pipeline.py produce --run-dir "$run_dir" 2>&1 | tail -1)
if echo "$produce" | grep -q '"status": "ok"'; then
  echo "OK $run_dir"
  echo "$produce"
  exit 0
fi
echo "FAIL $run_dir"
echo "$produce"
python3 scripts/lock_slot.py --run-dir "$run_dir" --status skipped 2>/dev/null || true
exit 1
