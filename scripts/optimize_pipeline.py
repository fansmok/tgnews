#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.runtime import load_dotenv, read_json, repo_root, write_json  # noqa: E402


def analyze_run_efficiency(run_dir: Path) -> dict:
    """Анализирует эффективность прогона: размеры артефактов, задержки, трудности."""
    report = {
        "run_id": run_dir.name,
        "token_waste_detected": [],
        "optimizations_applied": [],
        "recommendations": [],
    }

    # 1. Проверка размера handoff
    handoff_path = repo_root() / ".cursor" / "football-news-handoff.md"
    if handoff_path.exists():
        lines = len(handoff_path.read_text(encoding="utf-8").splitlines())
        if lines > 150:
            report["token_waste_detected"].append(f"handoff too long ({lines} lines)")
            report["recommendations"].append("сжать handoff: удалять логи завершённых прошлых ролей")

    # 2. Проверка трудностей
    difficulties_dir = run_dir / "difficulties"
    if difficulties_dir.exists():
        for diff_file in difficulties_dir.glob("*.json"):
            data = read_json(diff_file)
            if data.get("status") == "difficulty":
                role = data.get("role", diff_file.stem)
                report["token_waste_detected"].append(f"retry/difficulty in role {role}: {data.get('summary')}")

    # 3. Проверка артефактов дизайна и копирайта
    copy_path = run_dir / "copy.json"
    if copy_path.exists():
        copy_data = read_json(copy_path)
        if copy_data.get("engine") == "cursor":
            report["token_waste_detected"].append("Gemini was unavailable, cursor fallback used extra LLM tokens")

    design_path = run_dir / "design.json"
    if design_path.exists():
        design_data = read_json(design_path)
        if design_data.get("flux_error"):
            report["token_waste_detected"].append(f"Kie retry/fallback occurred: {design_data.get('flux_error')}")

    return report


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = repo_root() / run_dir

    analysis = analyze_run_efficiency(run_dir)
    write_json(run_dir / "optimization-audit.json", analysis)

    # Добавляем заметку в memory/optimization-notes.md, если найдены новые моменты
    notes_path = repo_root() / "memory" / "optimization-notes.md"
    if notes_path.exists() and (analysis["token_waste_detected"] or analysis["recommendations"]):
        existing = notes_path.read_text(encoding="utf-8")
        entry = f"\n- **{run_dir.name}**: "
        details = []
        if analysis["token_waste_detected"]:
            details.append("замечен перерасход: " + "; ".join(analysis["token_waste_detected"][:2]))
        if analysis["recommendations"]:
            details.append("рекомендация: " + "; ".join(analysis["recommendations"][:2]))
        entry += "; ".join(details)
        if entry not in existing:
            notes_path.write_text(existing + entry + "\n", encoding="utf-8")

    print(f"audit: {len(analysis['token_waste_detected'])} waste items, {len(analysis['recommendations'])} recommendations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
