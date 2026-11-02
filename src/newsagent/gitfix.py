from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ALLOWED_PREFIXES = (
    "agents/",
    "skills/",
    ".cursor/agents/",
    ".cursor/skills/",
    ".cursor/rules/",
    "shared/",
    "scripts/",
    "src/",
    "tests/",
    "memory/pipeline-fix-queue.md",
    "AGENTS.md",
    "README.md",
    "CURSOR-CLOUD-RUNBOOK.md",
    ".github/",
    "requirements.txt",
    "pytest.ini",
    ".gitignore",
)
SECRET_MARKERS = (
    "bot_token=",
    "api_hash=",
    "string_session=",
    "telegram_bot_token=",
    "telegram_string_session=",
    "telegram_login_session=",
    "gemini_api_key=",
    "kie_api_key=",
    "phone_code_hash=",
)


def git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def changed_files(repo: Path) -> list[str]:
    result = git(repo, ["status", "--porcelain"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    files: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.strip('"'))
    return files


def is_forbidden(path: str) -> bool:
    name = Path(path).name
    lowered = path.lower()
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    if name.endswith(".session") or name in {"news.db", "credentials.json"}:
        return True
    if "memory/runs/" in lowered or lowered.startswith(".cursor/football-news-handoff"):
        return True
    return False


def is_allowed(path: str) -> bool:
    if is_forbidden(path):
        return False
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def safe_remote(url: str) -> str:
    parts = urlsplit(url.strip())
    if not parts.scheme or "@" not in parts.netloc:
        return url.strip()
    host = parts.netloc.split("@", 1)[1]
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def diff_has_secret(repo: Path) -> bool:
    diff = git(repo, ["diff", "--cached"])
    text = diff.stdout.lower()
    return any(marker in text for marker in SECRET_MARKERS)


def commit_and_push(repo: Path, message: str, *, push: bool = True) -> dict:
    dirty = changed_files(repo)
    forbidden = [path for path in dirty if is_forbidden(path)]
    if forbidden:
        return {"status": "refused", "reason": "forbidden files", "files": forbidden}
    selected = [path for path in dirty if is_allowed(path)]
    if not selected:
        return {"status": "skipped", "reason": "no durable changes", "files": []}
    add = git(repo, ["add", "--", *selected])
    if add.returncode != 0:
        return {"status": "error", "reason": add.stderr.strip() or "git add failed"}
    if diff_has_secret(repo):
        git(repo, ["restore", "--staged", "--", *selected])
        return {"status": "refused", "reason": "secret in diff", "files": selected}
    commit = git(repo, ["commit", "-m", message])
    if commit.returncode != 0:
        return {"status": "error", "reason": commit.stderr.strip() or commit.stdout.strip() or "git commit failed"}
    sha = git(repo, ["rev-parse", "--short", "HEAD"]).stdout.strip()
    result = {"status": "committed", "commit": sha, "files": selected, "push": "skipped"}
    if not push:
        return result
    remote = git(repo, ["remote", "get-url", "origin"])
    if remote.returncode != 0:
        result["status"] = "needs-human"
        result["push"] = "no-origin"
        return result
    pushed = git(repo, ["push", "origin", "HEAD"])
    if pushed.returncode != 0:
        stderr = pushed.stderr.lower()
        if "no upstream" in stderr or "has no upstream" in stderr:
            pushed = git(repo, ["push", "-u", "origin", "HEAD"])
    if pushed.returncode != 0:
        result["status"] = "needs-human"
        result["push"] = "failed"
        result["reason"] = pushed.stderr.strip()
        return result
    result["status"] = "pushed"
    result["push"] = safe_remote(remote.stdout)
    return result
