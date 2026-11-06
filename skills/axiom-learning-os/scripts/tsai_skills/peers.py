"""Other students' work: Top Submissions galleries, GitHub handles, peer repos (all read-only).

Axiom shows a student only their own submissions (`/submissions` is 403 for students). Two routes
to other people's work:

1. Top Submissions: per-lecture galleries (only some lectures have one). Cards give the student's
   NAME and a live-app URL (Netlify etc.), not a GitHub handle.
2. GitHub: the lab repo's PR descriptions start with `Name:`, so PR author logins map to names.
   Then `gh repo list <login>` finds that student's public repos (later assignments are repos).
"""

from __future__ import annotations

import html as _html
import json
import re
import shutil
import subprocess
from typing import Any

from tsai_skills.client import ApiError

LAB_REPO = "theschoolofai/era-v5-lab"
CARD_RE = re.compile(
    r'<article class="card">.*?<div class="title"><a href="([^"]*)"[^>]*>(.*?)</a></div>'
    r'(?:<div class="desc">(.*?)</div>)?',
    re.S,
)
THUMB_RE = re.compile(r"url\('([^']+)'\)")


def parse_gallery(page: str) -> list[dict[str, str]]:
    """Gallery htmlContent → one row per card: student name, submission URL, description, thumbnail."""
    rows = []
    for m in CARD_RE.finditer(page):
        thumb = THUMB_RE.search(m.group(0))
        rows.append(
            {
                "student": _html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip(),
                "url": m.group(1).strip(),
                "description": _html.unescape(re.sub(r"<[^>]+>", "", m.group(3) or "")).strip(),
                "thumbnail": thumb.group(1) if thumb else "",
            }
        )
    return rows


def name_to_logins(prs: list[dict[str, Any]]) -> dict[str, list[str]]:
    """PR list (with ``body`` and ``author.login``) → {lowercased Name: [github logins]}."""
    out: dict[str, set[str]] = {}
    for p in prs:
        m = re.search(r"(?im)^\s*Name:\s*(.+?)\s*$", p.get("body") or "")
        login = (p.get("author") or {}).get("login")
        if m and login:
            out.setdefault(m.group(1).strip().casefold(), set()).add(login)
    return {k: sorted(v) for k, v in out.items()}


def repos_for_session(repos: list[dict[str, Any]], number: int) -> list[dict[str, Any]]:
    """Non-forks whose description says 'Session N' or whose name has an sN token."""
    desc = re.compile(rf"\bSession\s*0?{number}\b", re.I)
    name = re.compile(rf"(^|[-_])s0?{number}([-_]|$)", re.I)
    return [
        r for r in repos
        if not r.get("isFork") and (desc.search(r.get("description") or "") or name.search(r.get("name") or ""))
    ]


def _gh(args: list[str], timeout: int = 180) -> Any:
    if not shutil.which("gh"):
        raise ApiError("gh (GitHub CLI) not installed")
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise ApiError(f"gh {' '.join(args[:3])}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout or "null")


def lab_name_map(repo: str = LAB_REPO) -> dict[str, list[str]]:
    prs = _gh(["pr", "list", "-R", repo, "--state", "all", "--limit", "2000", "--json", "number,author,body"])
    return name_to_logins(prs)


def user_repos(login: str, session: int | None = None) -> list[dict[str, Any]]:
    repos = _gh(["repo", "list", login, "--limit", "200", "--json", "name,description,pushedAt,isFork,url"])
    return repos_for_session(repos, session) if session is not None else [r for r in repos if not r.get("isFork")]
