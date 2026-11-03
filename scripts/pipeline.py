#!/usr/bin/env python3
"""Механические этапы выпуска одним вызовом. Модель нужна только критику и при сбоях.

Этапы:
  gate     doctor + start_run + реклама + слот. Холостой запуск удаляет run_dir.
  scout    блокировка слота + новости дня + память.
  produce  текст/emoji/голос/caption и фото/карточка/ревью параллельно.
  rework   повтор после REWORK критика: --target fn-copy | fn-design.
  publish  validate --require-critic + publish.
  finish   сводка трудностей, аудит, prune; решает, нужен ли LLM-фиксер.

Каждый этап печатает одну строку JSON. Коды: 0 дальше, 2 штатная остановка, 1 ошибка.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsagent.design_review import extreme_design_issues  # noqa: E402
from newsagent.difficulties import collect_difficulties, report_difficulty  # noqa: E402
from newsagent.memory import connect, list_scheduled, occupied_slots, remember_story  # noqa: E402
from newsagent.runtime import iso, load_dotenv, now_msk, read_json, repo_root, write_json  # noqa: E402
from newsagent.schedule import batch_slots, next_publish, relocation_plan  # noqa: E402

HANDOFF = ROOT / ".cursor" / "football-news-handoff.md"


def run(script: str, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    lines = [line for line in (proc.stdout + proc.stderr).splitlines() if line.strip()]
    return proc.returncode, (lines[-1] if lines else "")


def emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return code


def note(block: str, lines: list[str]) -> None:
    if HANDOFF.exists():
        with HANDOFF.open("a", encoding="utf-8") as handle:
            handle.write(f"\n=== {block} ===\n" + "\n".join(lines) + "\n")


def report(run_dir: Path, role: str, problems: list[str], recovered: str = "", fix: str = "", files: str = "") -> None:
    context = run_dir / "context.json"
    run_id = read_json(context)["run_id"] if context.exists() else run_dir.name
    report_difficulty(
        run_dir,
        role=role,
        run_id=run_id,
        status="difficulty" if problems else "none",
        severity="medium" if problems else "low",
        summary="; ".join(problems),
        recovered=recovered,
        fix=fix,
        files=[item for item in files.split(",") if item],
    )


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root() / path


def _load_ads(run_dir: Path) -> list:
    payload = read_json(run_dir / "ads.json") if (run_dir / "ads.json").exists() else {}
    return payload.get("items") or payload.get("slots") or []


def _move_blocked(ads: list) -> list[dict]:
    """Переносит уже готовый пост с паузы на свободную минуту. Текст и карточка те же."""
    conn = connect(repo_root() / "memory" / "news.db")
    moved = []
    for item in relocation_plan(now_msk(), ads, list_scheduled(conn)):
        if item["status"] != "move":
            moved.append({"from": iso(item["from"]), "status": item["status"]})
            continue
        code, out = run(
            "move_slot.py",
            "--run-id",
            item["run_id"],
            "--from",
            iso(item["from"]),
            "--to",
            iso(item["to"]),
            "--message-id",
            item.get("message_id") or "",
        )
        moved.append(
            {
                "from": iso(item["from"]),
                "to": iso(item["to"]),
                "status": "moved" if code == 0 else "move_failed",
                "detail": out if code else "",
            }
        )
    return moved


def stage_day(args) -> int:
    """Один список всех постов, которые ещё надо поставить сегодня."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "doctor.py")], cwd=str(ROOT), capture_output=True, text=True
    )
    if proc.returncode != 0:
        bad = [line for line in proc.stdout.splitlines() if line.startswith(("ERROR", "WARN"))]
        return emit({"stage": args.stage, "status": "doctor_error", "issues": bad}, 1)
    code, out = run("start_run.py", "--run-id", f"dayplan-{now_msk().strftime('%Y%m%d')}")
    run_dir_rel = out.split("=", 1)[1] if out.startswith("run_dir=") else ""
    if code != 0 or not run_dir_rel:
        return emit({"stage": args.stage, "status": "start_error", "detail": out}, 1)
    run_dir = resolve(run_dir_rel)
    code, out = run("fetch_ads.py", "--run-dir", run_dir_rel)
    if code != 0:
        return emit({"stage": args.stage, "status": "ads_error", "detail": out}, 1)
    ads_payload = read_json(run_dir / "ads.json")
    write_json(repo_root() / "memory" / "day-ads.json", ads_payload)
    ads = _load_ads(run_dir)
    shutil.rmtree(run_dir, ignore_errors=True)
    conn = connect(repo_root() / "memory" / "news.db")
    cancelled = _move_blocked(ads)
    now = now_msk()
    slots = [
        {"publish_at": iso(item["publish_at"]), "reason": item["reason"]}
        for item in batch_slots(now, ads, occupied_slots(conn))
    ]
    if not slots:
        plan = next_publish(now, ads, occupied_slots(conn)) or {}
        return emit(
            {
                "stage": args.stage,
                "status": "idle",
                "next_publish_at": iso(plan["publish_at"]) if plan.get("publish_at") else None,
                "reason": plan.get("reason"),
                "moved": cancelled,
            },
            2,
        )
    return emit(
        {"stage": args.stage, "status": "batch", "slots": slots, "moved": cancelled, "count": len(slots)},
        0,
    )


def stage_gate(args) -> int:
    return stage_day(args)


def stage_scout(args) -> int:
    run_dir = resolve(args.run_dir)
    code, out = run("lock_slot.py", "--run-dir", args.run_dir)
    if code == 3:
        report(run_dir, "fn-scout", [])
        return emit({"stage": "scout", "status": "slot_busy"}, 2)
    code, out = run("fetch_news.py", "--run-dir", args.run_dir)
    problems = [] if code == 0 else [f"ленты недоступны: {out}"]
    code, out = run("pick_story.py", "--run-dir", args.run_dir)
    if code != 0:
        run("lock_slot.py", "--run-dir", args.run_dir, "--status", "skipped")
        report(run_dir, "fn-scout", problems + ["нет неопубликованной новости за день"], recovered="слот skipped")
        return emit({"stage": "scout", "status": "no_news"}, 2)
    story = read_json(run_dir / "story.json")
    report(run_dir, "fn-scout", problems, recovered="часть лент пропущена" if problems else "")
    note("FN-SCOUT", [f"story: {story.get('title')}", f"url: {story.get('url')}"])
    return emit(
        {
            "stage": "scout",
            "status": "ok",
            "title": story.get("title"),
            "clubs": story.get("clubs") or [],
            "action": story.get("action"),
        },
        0,
    )


def copy_chain(run_dir_rel: str, copy_ready: threading.Event | None = None) -> dict:
    result: dict = {"problems": []}
    code, out = run("write_copy.py", "--run-dir", run_dir_rel)
    if copy_ready is not None:
        copy_ready.set()
    if code == 3:
        result["needs_llm_copy"] = True
        result["problems"].append(f"Gemini не написал текст: {out}")
        return result
    if code != 0:
        result["problems"].append(f"write_copy: {out}")
        return result
    code, out = run("place_emoji.py", "--run-dir", run_dir_rel)
    if code != 0:
        result["problems"].append(f"place_emoji: {out}")
    code, out = run("write_voice.py", "--run-dir", run_dir_rel)
    if code == 3:
        write_json(resolve(run_dir_rel) / "voice.json", {"comment": None, "reason": "gemini_unavailable", "engine": "none"})
        result["problems"].append("Gemini не написал голос; пост без комментария")
    code, out = run("render_caption.py", "--run-dir", run_dir_rel)
    if code != 0:
        result["problems"].append(f"render_caption: {out}")
    return result


def design_chain(run_dir_rel: str, force: bool = False, copy_ready: threading.Event | None = None) -> dict:
    result: dict = {"problems": [], "notes": []}
    run_dir = resolve(run_dir_rel)
    if not force:
        code, out = run("fetch_photo.py", "--run-dir", run_dir_rel)
        if code != 0:
            result["problems"].append(f"фото не найдено: {out}")
            return result
    if copy_ready is not None:
        copy_ready.wait()
    if not (run_dir / "copy.json").exists():
        result["problems"].append("карточка не собрана: нет copy.json")
        return result
    code, out = run("compose_photo.py", "--run-dir", run_dir_rel, *(["--force"] if force else []))
    if code != 0:
        result["problems"].append(f"compose_photo: {out}")
        return result
    code, out = run("review_photo.py", "--run-dir", run_dir_rel)
    if code == 2 and not force:
        run("compose_photo.py", "--run-dir", run_dir_rel, "--force")
        code, out = run("review_photo.py", "--run-dir", run_dir_rel)
        result["notes"].append("карточка пересобрана после машинного ревью")
        if code == 2:
            result["problems"].append("карточка не прошла машинное ревью дважды")
    design = read_json(run_dir / "design.json") if (run_dir / "design.json").exists() else {}
    if design.get("flux_error"):
        result["notes"].append("Kie не ответил за 4 попытки, взято обычное фото")
    result["engine"] = design.get("engine")
    result["review"] = out.split("=", 1)[-1] if out else ""
    return result


def summary(run_dir: Path, copy: dict | None, design: dict | None) -> dict:
    payload: dict = {"stage": "produce"}
    if copy is not None:
        payload["copy"] = "needs_llm" if copy.get("needs_llm_copy") else ("ok" if not copy["problems"] else "issues")
    problems = (copy or {}).get("problems", []) + (design or {}).get("problems", [])
    if problems:
        payload["problems"] = problems
    if design is not None:
        payload["design_engine"] = design.get("engine")
        payload["photo_review"] = design.get("review")
        if design.get("notes"):
            payload["notes"] = design["notes"]
    code, out = run("validate_post.py", "--run-dir", str(run_dir))
    machine = read_json(run_dir / "machine.json") if (run_dir / "machine.json").exists() else {}
    failed = {name: item.get("detail", "") for name, item in (machine.get("checks") or {}).items() if item.get("status") != "PASS"}
    payload["machine"] = machine.get("status", "missing")
    if failed:
        payload["failed_checks"] = failed
    return payload


def reject_empty_reaction(run_dir: Path, payload: dict) -> bool:
    if "reaction" not in (payload.get("failed_checks") or {}):
        return False
    story_path = run_dir / "story.json"
    if story_path.exists():
        story = read_json(story_path)
        if story.get("url"):
            remember_story(connect(repo_root() / "memory" / "news.db"), story, "rejected")
    payload["status"] = "rejected"
    detail = str(payload["failed_checks"]["reaction"])
    payload["reason"] = "statement_without_content" if detail.startswith("заявление") else "reaction_without_words"
    return True


def stage_produce(args) -> int:
    run_dir = resolve(args.run_dir)
    copy_ready = threading.Event()
    with ThreadPoolExecutor(max_workers=2) as pool:
        copy_future = pool.submit(copy_chain, args.run_dir, copy_ready)
        design_future = pool.submit(design_chain, args.run_dir, False, copy_ready)
        copy, design = copy_future.result(), design_future.result()
    report(run_dir, "fn-copy", copy["problems"], recovered="см. produce", files="scripts/write_copy.py")
    report(run_dir, "fn-design", design["problems"], recovered="; ".join(design["notes"]), files="scripts/compose_photo.py")
    payload = summary(run_dir, copy, design)
    if copy.get("needs_llm_copy"):
        payload["status"] = "needs_llm_copy"
        return emit(payload, 3)
    if reject_empty_reaction(run_dir, payload):
        note("PRODUCE", ["rejected: нет слов первой стороны"])
        return emit(payload, 2)
    payload["status"] = "ok" if payload["machine"] == "PASS" else "machine_fail"
    note("PRODUCE", [f"copy: {payload.get('copy')}", f"design: {payload.get('design_engine')}", f"machine: {payload['machine']}"])
    return emit(payload, 0 if payload["machine"] == "PASS" else 1)


def stage_after_copy(args) -> int:
    """После ручного copy.json (Gemini недоступен): emoji, голос, caption, проверка."""
    run_dir = resolve(args.run_dir)
    problems = []
    for script in ("place_emoji.py", "render_caption.py"):
        code, out = run(script, "--run-dir", args.run_dir)
        if code != 0:
            problems.append(f"{script}: {out}")
    if not (run_dir / "voice.json").exists():
        code, _out = run("write_voice.py", "--run-dir", args.run_dir)
        if code != 0:
            write_json(run_dir / "voice.json", {"comment": None, "reason": "gemini_unavailable", "engine": "none"})
        run("render_caption.py", "--run-dir", args.run_dir)
    payload = summary(run_dir, None, None)
    payload["stage"] = "after_copy"
    payload["problems"] = problems
    return emit(payload, 0 if payload["machine"] == "PASS" else 1)


def stage_rework(args) -> int:
    run_dir = resolve(args.run_dir)
    critic = read_json(run_dir / "critic.json") if (run_dir / "critic.json").exists() else {}
    issues = critic.get("issues") or []
    if args.target == "fn-copy":
        write_json(run_dir / "rework.json", {"issues": issues})
        result = copy_chain(args.run_dir)
        report(run_dir, "fn-copy", ["REWORK критика: " + "; ".join(issues)] + result["problems"], recovered="текст переписан Gemini")
        payload = summary(run_dir, result, None)
        if result.get("needs_llm_copy"):
            payload["status"] = "needs_llm_copy"
            return emit(payload, 3)
    else:
        extreme = extreme_design_issues(issues)
        if not extreme:
            write_json(run_dir / "critic.json", {"verdict": "PASS", "target": "", "issues": []})
            return emit(
                {"stage": "rework", "status": "kept", "target": "fn-design", "reason": "card_usable"},
                0,
            )
        result = design_chain(args.run_dir, force=True)
        report(
            run_dir,
            "fn-design",
            ["REWORK критика: " + "; ".join(extreme)] + result["problems"],
            recovered="карточка пересобрана",
        )
        payload = summary(run_dir, None, result)
    payload["stage"] = "rework"
    (run_dir / "critic.json").unlink(missing_ok=True)
    return emit(payload, 0 if payload["machine"] == "PASS" else 1)


def stage_publish(args) -> int:
    run_dir = resolve(args.run_dir)
    code, out = run("validate_post.py", "--run-dir", args.run_dir, "--require-critic")
    if code != 0:
        report(run_dir, "fn-publish", [f"gate не пройден: {out}"])
        return emit({"stage": "publish", "status": "refused", "detail": out}, 1)
    code, out = run("publish.py", "--run-dir", args.run_dir)
    result = read_json(run_dir / "publish-result.json") if (run_dir / "publish-result.json").exists() else {}
    status = result.get("status") or out
    ok = code == 0 and status in {"send", "schedule", "sent", "scheduled", "dry_run"}
    report(run_dir, "fn-publish", [] if ok else [f"публикация: {status} {result.get('detail', '')}".strip()])
    note("FN-PUBLISH", [f"status: {status}", f"message_id: {result.get('message_id', '')}"])
    return emit(
        {
            "stage": "publish",
            "status": status,
            "publish_at": result.get("publish_at"),
            "message_id": result.get("message_id"),
            "mode": result.get("mode"),
        },
        0 if ok else 1,
    )


def stage_finish(args) -> int:
    run_dir = resolve(args.run_dir)
    payload = collect_difficulties(run_dir)
    run("optimize_pipeline.py", "--run-dir", args.run_dir)
    fixer = "needed" if payload["difficulties"] else "skip"
    hard = fixer == "needed"
    if fixer == "skip":
        report(run_dir, "fn-fixer", [])
        note("FN-FIXER", [f"difficulties: {payload['difficulties']}", "fixer: skip (скрипт, без LLM)"])
    run("prune_runs.py", "--days", "2", "--keep", "5")
    return emit(
        {
            "stage": "finish",
            "difficulties": payload["difficulties"],
            "fixer": fixer,
            "brief": str((run_dir / "fixer-brief.md").relative_to(repo_root())) if hard else "",
        },
        0,
    )


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["gate", "day", "scout", "produce", "after_copy", "rework", "publish", "finish"])
    parser.add_argument("--run-dir")
    parser.add_argument("--target", choices=["fn-copy", "fn-design"], default="fn-copy")
    args = parser.parse_args()
    if args.stage not in {"gate", "day"} and not args.run_dir:
        parser.error("--run-dir required")
    handlers = {
        "gate": stage_gate,
        "day": stage_day,
        "scout": stage_scout,
        "produce": stage_produce,
        "after_copy": stage_after_copy,
        "rework": stage_rework,
        "publish": stage_publish,
        "finish": stage_finish,
    }
    return handlers[args.stage](args)


if __name__ == "__main__":
    raise SystemExit(main())
