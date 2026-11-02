from __future__ import annotations

import re
from pathlib import Path

from newsagent.runtime import append_incident, read_json, write_json

SECRET_MARKERS = re.compile(
    r"(\b\d{6,12}:[A-Za-z0-9_-]{20,}\b|"
    r"(?:telegram[_-]?bot[_-]?token|gemini[_-]?api[_-]?key|kie[_-]?api[_-]?key|"
    r"api[_-]?hash|string[_-]?session|login[_-]?session|phone[_-]?code[_-]?hash)"
    r"\s*[:=]\s*\S+)",
    re.IGNORECASE,
)


class SecretInReport(RuntimeError):
    pass


def assert_no_secrets(*parts: str) -> None:
    for part in parts:
        if part and SECRET_MARKERS.search(part):
            raise SecretInReport("в отчёте о трудности нельзя записывать секреты")


def report_difficulty(
    run_dir: Path,
    *,
    role: str,
    run_id: str,
    status: str,
    severity: str = "low",
    category: str = "other",
    summary: str = "",
    recovered: str = "",
    fix: str = "",
    files: list[str] | None = None,
    queue_path: Path | None = None,
) -> dict:
    if status not in {"none", "difficulty"}:
        raise ValueError("status must be none or difficulty")
    files = files or []
    assert_no_secrets(summary, recovered, fix, " ".join(files))
    payload = {
        "role": role,
        "run_id": run_id,
        "status": status,
        "severity": severity,
        "category": category,
        "summary": summary.strip(),
        "recovered": recovered.strip(),
        "fix": fix.strip(),
        "files": files,
        "incident_id": "",
    }
    if status == "difficulty":
        payload["incident_id"] = append_incident(
            role=role,
            run_id=run_id,
            severity=severity,
            category=category,
            what=payload["summary"] or "трудность без описания",
            recovered=payload["recovered"] or "не указано",
            fix=payload["fix"] or "разобрать фиксеру",
            files=files or ["none"],
            queue_path=queue_path,
        )
    folder = run_dir / "difficulties"
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / f"{role}.json", payload)
    return payload


def collect_difficulties(run_dir: Path) -> dict:
    folder = run_dir / "difficulties"
    reports = []
    if folder.exists():
        for path in sorted(folder.glob("*.json")):
            reports.append(read_json(path))
    difficulties = [item for item in reports if item.get("status") == "difficulty"]
    clean = [item["role"] for item in reports if item.get("status") == "none"]
    lines = ["# Сводка трудностей для фиксера", ""]
    if not reports:
        lines.append("Роли не сдали ни одного отчёта.")
    elif not difficulties:
        lines.append("Трудностей нет. Роли: " + ", ".join(clean) + ".")
    else:
        lines.append(f"Трудностей: {len(difficulties)}.")
        for item in difficulties:
            lines.extend(
                [
                    "",
                    f"## {item.get('incident_id') or item.get('role')}",
                    f"- роль: {item.get('role')}",
                    f"- тяжесть: {item.get('severity')}",
                    f"- что случилось: {item.get('summary')}",
                    f"- как обошлись в этом выпуске: {item.get('recovered')}",
                    f"- что поправить насовсем: {item.get('fix')}",
                    "- файлы: " + ", ".join(f"`{name}`" for name in item.get("files") or []) or "не указаны",
                ]
            )
    brief = "\n".join(lines) + "\n"
    (run_dir / "fixer-brief.md").write_text(brief, encoding="utf-8")
    payload = {
        "reports": len(reports),
        "difficulties": len(difficulties),
        "clean_roles": clean,
        "incidents": [item.get("incident_id") for item in difficulties if item.get("incident_id")],
    }
    write_json(run_dir / "fixer-brief.json", payload)
    return payload
