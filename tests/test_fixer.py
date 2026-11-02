from pathlib import Path

import pytest

from newsagent.difficulties import SecretInReport, collect_difficulties, report_difficulty
from newsagent.gitfix import commit_and_push, safe_remote


def test_clean_role_does_not_open_an_incident(tmp_path: Path):
    queue = tmp_path / "queue.md"
    queue.write_text("# Pipeline fix queue\n", encoding="utf-8")
    report_difficulty(tmp_path, role="fn-voice", run_id="R-1", status="none", queue_path=queue)
    assert "status: open" not in queue.read_text(encoding="utf-8")
    brief = collect_difficulties(tmp_path)
    assert brief["difficulties"] == 0
    assert brief["clean_roles"] == ["fn-voice"]


def test_difficulty_is_recorded_for_the_fixer(tmp_path: Path):
    queue = tmp_path / "queue.md"
    queue.write_text("# Pipeline fix queue\n", encoding="utf-8")
    payload = report_difficulty(
        tmp_path,
        role="fn-photo",
        run_id="R-1",
        status="difficulty",
        severity="medium",
        category="api",
        summary="og:image вёл на логотип",
        recovered="взял кадр из RSS",
        fix="отбрасывать картинки с logo в адресе",
        files=["src/newsagent/photos.py"],
        queue_path=queue,
    )
    text = queue.read_text(encoding="utf-8")
    assert payload["incident_id"] in text
    assert "status: open" in text
    assert "og:image" in text
    brief = collect_difficulties(tmp_path)
    assert brief["difficulties"] == 1
    assert "логотип" in (tmp_path / "fixer-brief.md").read_text(encoding="utf-8")


def test_secret_never_lands_in_the_report(tmp_path: Path):
    queue = tmp_path / "queue.md"
    queue.write_text("# Pipeline fix queue\n", encoding="utf-8")
    with pytest.raises(SecretInReport):
        report_difficulty(
            tmp_path,
            role="fn-publish",
            run_id="R-1",
            status="difficulty",
            summary="токен bot_token=123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            queue_path=queue,
        )
    assert "bot_token" not in queue.read_text(encoding="utf-8")
    assert not (tmp_path / "difficulties").exists()


def test_remote_token_is_stripped_from_the_push_report():
    assert safe_remote("https://user:ghp_secret@github.com/acme/news.git") == "https://github.com/acme/news.git"


def _git(repo: Path, *args: str) -> None:
    import os
    import subprocess

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    subprocess.run(["git", *args], cwd=repo, check=True, env=env, capture_output=True)


def test_push_refuses_env_and_commits_only_durable_files(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    _git(tmp_path, "init")
    (tmp_path / "README.md").write_text("start\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=secret\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("start\n\nещё строка\n", encoding="utf-8")
    refused = commit_and_push(tmp_path, "fix: test", push=False)
    assert refused["status"] == "refused"
    (tmp_path / ".env").unlink()
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    committed = commit_and_push(tmp_path, "fix: записать трудность", push=False)
    assert committed["status"] == "committed"
    assert "README.md" in committed["files"]
