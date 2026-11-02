# Контракт инцидента

Fixer всегда последний. Он собирает отчёты ролей из `memory/runs/<run-id>/difficulties/`, чинит повторяемую причину и пушит долговечные файлы на GitHub. Секреты и значения токенов в отчёт не писать.

Роль сдаёт отчёт так:

```bash
python3 scripts/report_difficulty.py --run-dir <run_dir> --role fn-photo --status none
python3 scripts/report_difficulty.py --run-dir <run_dir> --role fn-photo --status difficulty \
  --severity medium --category api \
  --summary "что сломалось" --recovered "как вышли в этом выпуске" \
  --fix "что поправить насовсем" --files src/newsagent/photos.py
```

`--status difficulty` дописывает в очередь блок:

```markdown
## INC-YYYYMMDD-HHMM-role-category
status: open
run_date: YYYY-MM-DD
role: fn-agent
run_id: R-...
severity: low | medium | high | blocker
category: prompt | script | docs | env | api | handoff | qa | publish | other

### What went wrong
- ...

### How the agent recovered this run
- ...

### Durable fix needed before next run
- ...

### Suggested files to inspect/change
- `path`

### Secrets
- none recorded

### Fixer resolution
- pending
```

Fixer меняет только долговечные файлы: `agents/`, `skills/`, `shared/`, `scripts/`, `src/newsagent/`, очередь инцидентов. После правок запускает `python3 scripts/sync_cursor_tree.py`, проверки и `python3 scripts/push_fixes.py`. Статус становится `fixed` или `needs-human`. В handoff он отдаёт директору сводку `=== FN-FIXER ===`.
