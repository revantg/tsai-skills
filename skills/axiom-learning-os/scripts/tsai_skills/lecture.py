"""Everything attached to a lecture, plus the capstone view.

A lecture (session) has: lesson markdown, embedded /widgets/*.html (full HTML + the JSON data in
their scripts), a transcript (Google Doc link at the end of the lesson), YouTube videos (studio
recording + live class), a chat channel (S<n>), an assignment (+ own submission and grade) and
sometimes a quiz. All of it hangs off ``session.id``.

All HTTP here is GET. Widgets and Google Docs are public and fetched without the session cookie.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tsai_skills.chat import chat_dump, dump_json, ist, list_channels, write_chat_dir
from tsai_skills.client import ApiError, AxiomClient

UA = "tsai-skills/0.1 (+headless; https://axiom.theschoolofai.in)"
WIDGET_RE = re.compile(r'src="(/widgets/[^"]+)"')
DOC_RE = re.compile(r"docs\.google\.com/document/d/([\w-]+)")
YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/embed/|youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,})", re.I
)
MEET_RE = re.compile(r"https?://meet\.google\.com/[a-z0-9-]+", re.I)
JS_DECL_RE = re.compile(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?=[\[{])")
SESSION_NO_RE = re.compile(r"^\s*Session\s+(\d+)\b", re.I)
CAPSTONE_RE = re.compile(r"^\s*(capstone|CAP)\b", re.I)


# ── pure helpers (unit-tested) ────────────────────────────────────────────────


def lesson_markdown(session: dict[str, Any]) -> str:
    return "\n\n".join(
        (l.get("markdownContent") or "") for l in session.get("lessons") or [] if isinstance(l, dict)
    )


def widget_paths(markdown: str) -> list[str]:
    return list(dict.fromkeys(WIDGET_RE.findall(markdown)))


def doc_ids(text: str) -> list[str]:
    return list(dict.fromkeys(DOC_RE.findall(text)))


def widget_data(html: str) -> dict[str, Any]:
    """Top-level ``const|let|var NAME = [..]|{..}`` literals that are strict JSON."""
    out: dict[str, Any] = {}
    dec = json.JSONDecoder()
    for m in JS_DECL_RE.finditer(html):
        try:
            out[m.group(1)] = dec.raw_decode(html, m.end())[0]
        except ValueError:
            continue  # JS object literal (unquoted keys): the full HTML is still saved
    return out


def html_text(html: str) -> str:
    """Visible text; <script> bodies are kept because widget data usually lives there."""
    t = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", html)
    t = re.sub(r"(?is)<script[^>]*>(.*?)</script>", lambda m: f"\n[script]\n{m.group(1)}\n[/script]\n", t)
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d|section)>", "\n", t)
    t = re.sub(r"<(?!/?script)[^>]+>", " ", t)
    import html as _h

    t = _h.unescape(t)
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", t)).strip() + "\n"


def session_number(title: str) -> int | None:
    m = SESSION_NO_RE.match(title or "")
    return int(m.group(1)) if m else None


def is_capstone(session: dict[str, Any]) -> bool:
    return bool(CAPSTONE_RE.search(session.get("title") or "")) or (session.get("order") or 0) >= 90


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


def session_dirname(s: dict[str, Any]) -> str:
    n = session_number(s.get("title") or "")
    return f"s{n:02d}-{slug(s['title'])}" if n is not None else slug(s["title"])


def resolve_session(sessions: list[dict[str, Any]], ref: str) -> dict[str, Any]:
    """Exact id → 'Session N' number (16, S16) → unique case-insensitive title fragment."""
    ref = ref.strip()
    for s in sessions:
        if s.get("id") == ref:
            return s
    m = re.fullmatch(r"[sS]?(\d+)", ref)
    if m:
        hit = [s for s in sessions if session_number(s.get("title") or "") == int(m.group(1))]
        if len(hit) == 1:
            return hit[0]
    hit = [s for s in sessions if ref.lower() in (s.get("title") or "").lower()]
    if len(hit) == 1:
        return hit[0]
    names = [f"{s.get('title')}" for s in (hit or sessions)]
    raise ApiError(f"session {ref!r} matched {len(hit)}; candidates: {names}")


def assignments_for(session: dict[str, Any], assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Linked by ``assignment.sessionId`` (all 15 live assignments carry it)."""
    return [a for a in assignments if isinstance(a, dict) and a.get("sessionId") == session["id"]]


def quizzes_for(session: dict[str, Any], quizzes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [q for q in quizzes if isinstance(q, dict) and q.get("sessionId") == session["id"]]


def session_videos(session: dict[str, Any]) -> list[dict[str, str]]:
    """``studioVideoHtml`` = lecture recording, ``gmeetVideoHtml`` = live-class recording."""
    rows: list[dict[str, str]] = []
    for role, text in (
        ("studio", session.get("studioVideoHtml") or ""),
        ("gmeet", session.get("gmeetVideoHtml") or ""),
        ("lesson", lesson_markdown(session)),
    ):
        for vid in YOUTUBE_RE.findall(text):
            if all(r["id"] != vid for r in rows):
                rows.append({"role": role, "id": vid, "url": f"https://www.youtube.com/watch?v={vid}"})
    return rows


def parse_time(text: str) -> float:
    """'5100', '84:05', '1:24:05', '1h24m5s' → seconds."""
    t = text.strip().lower()
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s?)?", t)
    if m and any(m.groups()) and not re.fullmatch(r"\d+(?:\.\d+)?", t):
        h, mi, s = (float(x or 0) for x in m.groups())
        return h * 3600 + mi * 60 + s
    if ":" in t:
        secs = 0.0
        for part in t.split(":"):
            secs = secs * 60 + float(part)
        return secs
    return float(t)


def srt_to_text(srt: str) -> str:
    """SRT/auto-caption → '[HH:MM] text …' one line per minute, rolling duplicates removed."""
    last = ""
    per_min: dict[str, list[str]] = {}
    for block in srt.strip().split("\n\n"):
        lines = block.split("\n")
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        minute = lines[1][:5]
        for line in lines[2:]:
            line = re.sub(r"<[^>]+>", "", line).strip()
            if line and line != last:
                per_min.setdefault(minute, []).append(line)
                last = line
    return "\n".join(f"[{k}] {' '.join(v)}" for k, v in per_min.items()) + "\n"


def find_plan_sheet(widget_vars: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """The capstone plan-sheet widget: a data object holding both ``teams`` and ``packs``."""
    for variables in widget_vars.values():
        for value in variables.values():
            if isinstance(value, dict) and "teams" in value and "packs" in value:
                return value
    return None


def my_teams(plan: dict[str, Any], my_name: str) -> dict[str, Any]:
    """My packs row + core / week-2 / week-3 teams with lead, roster, rotation peers, tasks."""
    row = next(
        (p for p in plan.get("packs") or [] if str(p.get("student", "")).casefold() == my_name.casefold()),
        None,
    )
    if row is None:
        return {"row": None, "teams": {}}
    by_id = {t["id"]: t for t in plan.get("teams") or []}
    out: dict[str, Any] = {}
    for role, key in (("core", "coreId"), ("week2", "w2Id"), ("week3", "w3Id")):
        tid = row.get(key)
        t = by_id.get(tid)
        if t is None:
            continue
        sid = str(tid)
        out[role] = {
            "id": tid,
            "name": t.get("name"),
            "lead": (plan.get("leads") or {}).get(sid),
            "scope": t.get("scope"),
            "mission": t.get("mission"),
            "milestones": t.get("milestones"),
            "bars": t.get("bars"),
            "weeks": t.get("weeks"),
            "coreRoster": (plan.get("roster") or {}).get(sid),
            "rotationIn": (plan.get("rotIn") or {}).get(sid),
        }
    return {"row": {k: v for k, v in row.items() if k != "url"}, "teams": out}


# ── network helpers ───────────────────────────────────────────────────────────


def fetch_public(url: str, timeout: float = 60.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as e:
        raise ApiError(f"GET {url}: {e}") from e


def fetch_widget(base_url: str, path: str) -> dict[str, Any]:
    html = fetch_public(base_url.rstrip("/") + path)
    return {"path": path, "html": html, "text": html_text(html), "data": widget_data(html)}


def export_doc(doc_id: str) -> str:
    """Public Google Doc → plain text. Raises if the doc is not link-shared."""
    text = fetch_public(f"https://docs.google.com/document/d/{doc_id}/export?format=txt")
    if re.match(r"\s*<(!doctype|html)", text, re.I):
        raise ApiError(f"Google Doc {doc_id} is not public (got an HTML sign-in page)")
    return text


def captions(video_id: str) -> str:
    """YouTube (auto-)captions → timestamped text. Needs yt-dlp; used when a lecture has no doc."""
    if not shutil.which("yt-dlp"):
        raise ApiError("yt-dlp not installed")
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(
            [
                "yt-dlp", "-q", "--no-warnings", "--skip-download", "--write-auto-subs", "--write-subs",
                "--sub-langs", "en.*", "--convert-subs", "srt", "-o", f"{d}/v.%(ext)s",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            check=False, capture_output=True, timeout=300,
        )
        files = sorted(Path(d).glob("*.srt"), key=lambda p: ("orig" in p.name, p.name))
        if not files:
            raise ApiError(f"no captions available for {video_id}")
        return srt_to_text(files[0].read_text(encoding="utf-8", errors="replace"))


def video_frames(video: str, times: list[str], out_dir: Path) -> list[Path]:
    """One PNG per timestamp: yt-dlp resolves the stream URL, ffmpeg seeks (no full download)."""
    for tool in ("yt-dlp", "ffmpeg"):
        if not shutil.which(tool):
            raise ApiError(f"{tool} not installed")
    m = YOUTUBE_RE.search(video)
    vid = m.group(1) if m else video
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,}", vid):
        raise ApiError(f"not a YouTube id or URL: {video!r}")
    got = subprocess.run(
        ["yt-dlp", "-q", "--no-warnings", "-f", "bv*[height<=720]/b", "-g", f"https://www.youtube.com/watch?v={vid}"],
        capture_output=True, text=True, timeout=120,
    )
    stream = (got.stdout.strip().splitlines() or [""])[0]
    if not stream:
        raise ApiError(f"yt-dlp could not resolve a stream for {vid}: {got.stderr.strip()[:200]}")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in times:
        secs = parse_time(t)
        h, rem = divmod(int(secs), 3600)
        path = out_dir / f"{vid}_{h:02d}{rem // 60:02d}{rem % 60:02d}.png"
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(secs), "-i", stream, "-frames:v", "1", "-y", str(path)],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0 or not path.exists():
            raise ApiError(f"ffmpeg failed at {t}: {r.stderr.strip()[:200]}")
        paths.append(path)
    return paths


# ── bundles ───────────────────────────────────────────────────────────────────


def lecture_index(
    sessions: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    quizzes: list[dict[str, Any]],
    channels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for s in sorted(sessions, key=lambda x: x.get("order") or 0):
        md = lesson_markdown(s)
        chan = [c["label"] for c in channels if c.get("sessionId") == s["id"] and c.get("type") == "session"]
        rows.append(
            {
                "order": s.get("order"),
                "number": session_number(s.get("title") or ""),
                "id": s["id"],
                "title": s.get("title"),
                "status": s.get("status"),
                "opensAt": ist(s["opensAt"]) if s.get("opensAt") else None,
                "widgets": len(widget_paths(md)),
                "transcriptDocs": doc_ids(md),
                "videos": [f"{v['role']}:{v['id']}" for v in session_videos(s)],
                "chat": chan,
                "assignments": [a.get("title") for a in assignments_for(s, assignments)],
                "quizzes": [q.get("title") for q in quizzes_for(s, quizzes)],
            }
        )
    return rows


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@dataclass
class Ctx:
    assignments: list[dict[str, Any]]
    quizzes: list[dict[str, Any]]
    me_id: str | None
    chat: bool
    pretty: bool


def _context(client: AxiomClient, course_id: str, chat: bool, pretty: bool) -> Ctx:
    return Ctx(
        assignments=[a for a in client.get_assignments(course_id) if isinstance(a, dict)],
        quizzes=[q for q in client.get_quizzes(course_id) if isinstance(q, dict)],
        me_id=(client.get_me() or {}).get("id"),
        chat=chat,
        pretty=pretty,
    )


def _bundle(
    client: AxiomClient, course_id: str, s: dict[str, Any], out: Path, ctx: Ctx
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    assignments, quizzes, me_id, chat, pretty = ctx.assignments, ctx.quizzes, ctx.me_id, ctx.chat, ctx.pretty
    errors: list[str] = []
    md = lesson_markdown(s)
    _write(out / "lesson.md", md)
    _write(out / "session.json", dump_json({k: v for k, v in s.items() if k != "lessons"}, pretty))

    # widgets: full HTML + extracted text + parsed JSON data
    widgets, widget_vars = [], {}
    for path in widget_paths(md):
        name = Path(path).stem
        try:
            w = fetch_widget(client.base_url, path)
        except ApiError as e:
            errors.append(f"widget {path}: {e}")
            continue
        _write(out / "widgets" / f"{name}.html", w["html"])
        _write(out / "widgets" / f"{name}.txt", w["text"])
        if w["data"]:
            _write(out / "widgets" / f"{name}.data.json", dump_json(w["data"], pretty))
            widget_vars[name] = w["data"]
        widgets.append({"name": name, "path": path, "dataVars": sorted(w["data"])})

    # videos + transcript (Google Doc first, YouTube captions as fallback)
    videos = session_videos(s)
    ids = doc_ids(md + (s.get("studioVideoHtml") or ""))
    transcript: dict[str, Any] = {"source": None, "docIds": ids, "files": []}
    for i, d in enumerate(ids):
        try:
            name = "transcript.txt" if i == 0 else f"transcript_{i + 1}.txt"
            _write(out / name, export_doc(d))
            transcript["files"].append(name)
            transcript["source"] = "google-doc"
        except ApiError as e:
            errors.append(f"transcript {d}: {e}")
    if not transcript["files"] and videos:
        try:
            _write(out / "transcript_captions.txt", captions(videos[0]["id"]))
            transcript.update(source="youtube-captions", files=["transcript_captions.txt"], videoId=videos[0]["id"])
        except ApiError as e:
            errors.append(f"captions {videos[0]['id']}: {e}")

    # assignment + own submission + grade
    adata = []
    for a in assignments_for(s, assignments):
        row: dict[str, Any] = {"assignment": a}
        for key, fn in (("submission", client.get_assignment_submission), ("grade", client.get_assignment_grade)):
            try:
                row[key] = fn(a["id"])
            except ApiError as e:
                row[key] = None
                errors.append(f"{key} {a['id']}: {e}")
        adata.append(row)
    _write(out / "assignments.json", dump_json(adata, pretty))

    # quizzes: questions/answers only exist once attempted (never start an attempt)
    qdata = []
    for q in quizzes_for(s, quizzes):
        row = {"quiz": q, "attempt": None, "questions": None}
        if q.get("hasUserAttempt"):
            for key, fn in (("attempt", client.get_quiz_attempt), ("questions", client.get_quiz_questions)):
                try:
                    row[key] = fn(q["id"])
                except ApiError as e:
                    errors.append(f"quiz {key} {q['id']}: {e}")
        qdata.append(row)
    _write(out / "quizzes.json", dump_json(qdata, pretty))

    # chat: the lecture's own channel, plus team groups I belong to (capstone)
    chat_files: list[str] = []
    if chat:
        def keep(c: dict[str, Any]) -> bool:
            if c.get("sessionId") != s["id"]:
                return False
            if c.get("type") == "group":
                return any(g.get("userId") == me_id for g in c.get("groupMembers") or [])
            return True

        data = chat_dump(client, course_id, keep=keep, roster=False)
        if data["channels"]:
            write_chat_dir(data, out / "chat", pretty)
            chat_files = sorted(p.name for p in (out / "chat").glob("*.md"))

    index = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "session": {k: s.get(k) for k in ("id", "title", "order", "status", "opensAt", "closesAt")},
        "opensAtIST": ist(s["opensAt"]) if s.get("opensAt") else None,
        "lessonChars": len(md),
        "widgets": widgets,
        "videos": videos,
        "transcript": transcript,
        "assignments": [
            {
                "id": r["assignment"]["id"],
                "title": r["assignment"].get("title"),
                "dueAt": ist(r["assignment"]["dueAt"]) if r["assignment"].get("dueAt") else None,
                "submitted": r["submission"] is not None,
                "graded": r["grade"] is not None,
            }
            for r in adata
        ],
        "quizzes": [
            {"id": r["quiz"]["id"], "title": r["quiz"].get("title"), "attempted": bool(r["quiz"].get("hasUserAttempt"))}
            for r in qdata
        ],
        "chatFiles": chat_files,
        "errors": errors,
    }
    _write(out / "lecture.json", dump_json(index, pretty))
    return index, widget_vars


def lecture_bundle(
    client: AxiomClient, course_id: str, session_ref: str, out_dir: Path, pretty: bool = True
) -> list[dict[str, Any]]:
    """Write one folder per lecture. ``session_ref`` may be an id, 16 / S16, a title fragment, or 'all'."""
    sessions = [s for s in client.get_sessions(course_id) if isinstance(s, dict)]
    ctx = _context(client, course_id, chat=True, pretty=pretty)
    chosen = sessions if session_ref.lower() == "all" else [resolve_session(sessions, session_ref)]
    return [_bundle(client, course_id, s, out_dir / session_dirname(s), ctx)[0] for s in chosen]


def _mine(m: dict[str, Any], me: dict[str, Any]) -> bool:
    first = (str(me.get("name") or "").split() or [""])[0].casefold()
    body = str(m.get("body") or "").casefold()
    reply = m.get("replyTo") if isinstance(m.get("replyTo"), dict) else {}
    named = bool(first) and re.search(rf"\b{re.escape(first)}\b", body) is not None
    return (
        me.get("id") in (m.get("mentions") or [])
        or reply.get("userName") == me.get("name")
        or (named and m.get("userName") != me.get("name"))
    )


def capstone_bundle(
    client: AxiomClient, course_id: str, out_dir: Path, pretty: bool = True, all_groups: bool = False
) -> dict[str, Any]:
    """Capstone sessions (lessons, widgets, transcripts), my teams from the plan sheet, full group chats."""
    me = client.get_me() or {}
    sessions = [s for s in client.get_sessions(course_id) if isinstance(s, dict)]
    channels = list_channels(client, course_id)
    ctx = _context(client, course_id, chat=False, pretty=pretty)
    cap_sessions = [s for s in sessions if is_capstone(s)]
    lectures, widget_vars = [], {}
    for s in cap_sessions:
        index, wv = _bundle(client, course_id, s, out_dir / "lectures" / session_dirname(s), ctx)
        lectures.append(index)
        widget_vars.update({f"{session_dirname(s)}/{k}": v for k, v in wv.items()})

    plan = find_plan_sheet(widget_vars)
    mine = my_teams(plan, me.get("name", "")) if plan else {"row": None, "teams": {}}
    team_ids = {t["id"] for t in mine["teams"].values()}

    def keep(c: dict[str, Any]) -> bool:
        if c.get("type") == "dm" or (c.get("type") == "session" and c.get("sessionId") in {s["id"] for s in cap_sessions}):
            return True
        if c.get("type") != "group":
            return False
        mem = any(g.get("userId") == me.get("id") for g in c.get("groupMembers") or [])
        num = re.match(r"\s*(\d+)", c.get("groupName") or "")
        return all_groups or mem or bool(num and int(num.group(1)) in team_ids)

    data = chat_dump(client, course_id, keep=keep, roster=False)
    write_chat_dir(data, out_dir / "chat", pretty)

    brief, mentions = [], []
    for c in data["channels"]:
        for m in data["messages"].get(c["label"]) or []:
            line = f"### [{c['label']} {c.get('groupName') or ''}] {ist(m['createdAt'])} · {m.get('userName')} ({m.get('userRole')})\n\n{m.get('body')}\n"
            if m.get("userRole") != "student" and c["type"] != "dm":
                brief.append(line)
            if _mine(m, me):
                mentions.append(line)
    _write(out_dir / "admin_posts.md", "# Admin (TSAI) posts, all times IST\n\n" + "\n".join(brief))
    _write(out_dir / "mentions.md", f"# Messages that mention or reply to {me.get('name')}, all times IST\n\n" + "\n".join(mentions))

    summary = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "me": {k: me.get(k) for k in ("id", "name", "githubUsername")},
        "planSheetUpdated": plan.get("updated") if plan else None,
        "planSheetLinksUntil": plan.get("links_until") if plan else None,
        "myRow": mine["row"],
        "myTeams": mine["teams"],
        "myChannels": [{k: c.get(k) for k in ("label", "groupName", "canPost")} for c in data["channels"]],
        "lectures": [{"title": l["session"]["title"], "transcript": l["transcript"]["source"], "widgets": len(l["widgets"])} for l in lectures],
        "messageCounts": {k: len(v) for k, v in data["messages"].items()},
        "errors": [e for l in lectures for e in l["errors"]],
        "note": "Plan-sheet pack/tokenizer download URLs are signed and expire; they stay in lectures/*/widgets only. Never commit this folder.",
    }
    _write(out_dir / "capstone.json", dump_json(summary, pretty))

    md = [f"# Capstone view for {me.get('name')}", ""]
    if mine["row"]:
        r = mine["row"]
        md += [f"Pack `{r.get('pack')}` ({r.get('lang')}, {r.get('source')}). Plan sheet updated {summary['planSheetUpdated']}.", ""]
    else:
        md += ["**No packs row found for this name** in the plan sheet.", ""]
    for role, t in mine["teams"].items():
        md += [f"## {role}: {t['id']}. {t['name']} (lead {t['lead']})", f"{t['mission']}", ""]
        if t.get("milestones"):
            md += ["Milestones: " + "; ".join(f"{m['label']} ({m['date']})" for m in t["milestones"]), ""]
        wk = {"core": None, "week2": 2, "week3": 3}[role]
        for w in t.get("weeks") or []:
            if wk is None or w.get("week") == wk:
                md += [f"### Week {w['week']}: {w['focus']}", "Team tasks:"] + [f"- {x}" for x in w.get("students") or []]
                if role != "core" and w.get("rotation"):
                    md += ["Your rotation task:"] + [f"- {x}" for x in w["rotation"]]
                md += [f"Gate: {w.get('gate')}", ""]
        if t.get("rotationIn"):
            if role == "core":
                members = [f"{k} rotators: {', '.join(v)}" for k, v in t["rotationIn"].items()]
            else:
                key = "w2" if role == "week2" else "w3"
                members = [f"this week's rotators ({key}): {', '.join(t['rotationIn'].get(key) or [])}"]
            md += ["Rotation members, " + "; ".join(members), ""]
    _write(out_dir / "capstone.md", "\n".join(md) + "\n")
    return summary
