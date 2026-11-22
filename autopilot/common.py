"""Shared helpers: config, persistent state (committed back to the repo), GitHub issues."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
STATE.mkdir(exist_ok=True)


def cfg() -> dict:
    return json.loads((ROOT / "autopilot" / "config.json").read_text())


def load(name: str, default):
    p = STATE / name
    return json.loads(p.read_text()) if p.exists() else default


def save(name: str, data):
    p = STATE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False))


def has_youtube_secrets() -> bool:
    return all(os.getenv(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


# ------------------------------------------------------------------ GitHub
def _gh(method, path, **kw):
    tok, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if not tok or not repo:
        print(f"[github] {method} {path} skipped (not running in GitHub Actions)")
        return None
    r = requests.request(method, f"https://api.github.com/repos/{repo}{path}", timeout=30, headers={
        "Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}, **kw)
    r.raise_for_status()
    return r.json() if r.text else None


def create_issue(title: str, body: str, labels: list[str]) -> int | None:
    d = _gh("POST", "/issues", json={"title": title, "body": body[:65000], "labels": labels})
    return d["number"] if d else None


def comment(issue: int, body: str):
    _gh("POST", f"/issues/{issue}/comments", json={"body": body[:65000]})


def add_labels(issue: int, labels: list[str]):
    _gh("POST", f"/issues/{issue}/labels", json={"labels": labels})


def run_url() -> str:
    s, r, i = os.getenv("GITHUB_SERVER_URL"), os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_RUN_ID")
    return f"{s}/{r}/actions/runs/{i}" if s and r and i else "(local run)"


def skill_tool(script: str, *args: str) -> list:
    """Run one of the vendored youtube-agent-skill tools with --json and return its parsed output."""
    out = subprocess.run([sys.executable, str(ROOT / "vendor/youtube-agent-skill/skills" / script), "--json", *args],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)
