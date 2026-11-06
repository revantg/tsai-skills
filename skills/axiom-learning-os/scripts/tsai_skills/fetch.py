#!/usr/bin/env python3
"""Fetch any verified Axiom Learning OS entity over the student cookie APIs.

Examples:
  scripts/fetch.sh courses
  scripts/fetch.sh sessions --course-id CID
  scripts/fetch.sh enrolled-summary
  scripts/fetch.sh course-bundle --course-id CID --out-dir out/c
  scripts/fetch.sh all --out-dir out/all
  scripts/fetch.sh chat-messages --course-id CID --channel G5
  scripts/fetch.sh chat-dump --course-id CID --out-dir out/chat
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tsai_skills.auth import ensure_authenticated_token, resolve_token
from tsai_skills.chat import chat_dump, dump_json, resolve_channel, write_chat_dir
from tsai_skills.client import ApiError, AuthError, AxiomClient, DEFAULT_BASE
from tsai_skills.lecture import (
    MEET_RE,
    YOUTUBE_RE,
    capstone_bundle,
    export_doc,
    fetch_widget,
    lecture_bundle,
    lecture_index,
    resolve_session,
    video_frames,
)
from tsai_skills.peers import lab_name_map, parse_gallery, user_repos
from tsai_skills.schema import extract_lesson_markdown

ENTITIES: dict[str, str] = {
    "session": "Auth session (user + expires)",
    "me": "Student profile (/api/me)",
    "courses": "Enrolled courses list",
    "course": "Single course metadata (needs --course-id)",
    "sessions": "Class sessions + lessons/markdown/video HTML",
    "assignments": "Assignments for a course",
    "quizzes": "Quizzes for a course",
    "quiz": "Single quiz metadata (needs --quiz-id)",
    "grades": "Grade rows (optional --course-id filter)",
    "grades-summary": "Per-course grade totals (grades page)",
    "submission": "Own submission for assignment (needs --assignment-id)",
    "assignment-grade": "Grade for one assignment (needs --assignment-id)",
    "flashcards": "Course flashcards (needs --course-id)",
    "dashboard-flashcards": "Flashcard progress per course",
    "dashboard-student": "Standing, trajectory, weak areas, feed",
    "dashboard": "Home dashboard (courses, deadlines, activity)",
    "notifications": "Bell notifications",
    "announcements": "Course announcements (needs --course-id)",
    "daily-check": "Daily check-in items",
    "chat-courses": "Chat sidebar courses + unread",
    "chat-channels": "Chat channels for a course (G, S1.., CAP, G1..G12 groups, DM)",
    "chat-messages": "Full history of one channel (needs --course-id --channel LABEL|ID)",
    "chat-dump": "Every channel → JSON + one markdown per channel (needs --course-id --out-dir)",
    "chat-roster": "All course members + online flag (needs --course-id)",
    "chat-search": "Search chat (needs --course-id --query; optional --channel)",
    "search": "Global ⌘K search: courses/sessions/assignments/chat (needs --query)",
    "calendar": "Dated events (optional --course-id)",
    "feed": "Shared reading links (optional --course-id)",
    "scorecard": "Weighted category scorecard (needs --course-id)",
    "galleries": "Top Submissions galleries (needs --course-id; --gallery-id for one)",
    "lesson": "One lesson by id (needs --lesson-id)",
    "quiz-questions": "Quiz questions + answers once taken (needs --quiz-id)",
    "quiz-attempt": "Own quiz attempt + score (needs --quiz-id)",
    "notification-prefs": "Notification toggles",
    "invites": "Pending invites",
    "lessons": "Flattened lesson markdown from sessions",
    "media": "YouTube + GMeet index from sessions",
    "enrolled-summary": "Whoami + enrolled courses + standing + grades totals",
    "course-bundle": "Full dump for one course (many endpoints)",
    "lectures": "Index of every lecture: widgets, transcript docs, videos, chat, assignment, quiz (needs --course-id)",
    "lecture": "One lecture or 'all' → folder with lesson, widgets, transcript, videos, chat, assignment+submission+grade, quiz (needs --course-id --session --out-dir)",
    "capstone": "Capstone: lectures+widgets+transcripts, my teams/rotations from the plan sheet, full group chats (needs --course-id --out-dir; optional --all-groups)",
    "widget": "One /widgets/<name>.html: full HTML + text + parsed data (needs --widget, optional --out-dir)",
    "transcript": "Google Doc transcript as text (needs --doc-id, optional -o)",
    "video-frame": "PNG stills from a YouTube video at timestamps (needs --video --at 1:24:05,1:30:00 --out-dir; no login)",
    "gallery-cards": "Top Submissions parsed to rows (student name, submission URL, description). Needs --course-id; optional --session or --gallery-id; most lectures have no gallery",
    "peers": "Other students on GitHub: name → login from lab PR 'Name:' lines, then their repos (optional --query NAME, --session N); uses gh, no Axiom login",
    "all": "enrolled-summary + course-bundle for each enrolled course",
}


def _dump(data: Any, pretty: bool = True) -> str:
    return dump_json(data, pretty)


def _write_out(data: Any, out: Path | None, pretty: bool) -> int:
    text = _dump(data, pretty=pretty)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def _as_list(payload: Any) -> list[Any]:
    return payload if isinstance(payload, list) else []


def extract_media(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for s in sessions:
        if not isinstance(s, dict):
            continue
        html = (s.get("studioVideoHtml") or "") + "\n" + (s.get("gmeetVideoHtml") or "")
        md = "\n".join(
            (lesson.get("markdownContent") or "")
            for lesson in (s.get("lessons") or [])
            if isinstance(lesson, dict)
        )
        blob = html + "\n" + md
        yt = list(dict.fromkeys(YOUTUBE_RE.findall(blob)))
        meet = list(dict.fromkeys(MEET_RE.findall(blob)))
        rows.append(
            {
                "sessionId": s.get("id"),
                "sessionTitle": s.get("title"),
                "order": s.get("order"),
                "status": s.get("status"),
                "youtubeIds": yt,
                "youtubeUrls": [f"https://www.youtube.com/watch?v={i}" for i in yt],
                "meetUrls": meet,
                "lessonCount": len(s.get("lessons") or []),
            }
        )
    return rows


def enrolled_summary(client: AxiomClient) -> dict[str, Any]:
    session = client.get_session()
    courses = _as_list(client.get_courses())
    grades_sum = _as_list(client.get_grades_summary())
    dash = client.get_dashboard_student() or {}
    flash = _as_list(client.get_dashboard_flashcards())
    by_course_grades = {
        g.get("courseId"): g for g in grades_sum if isinstance(g, dict)
    }
    by_course_flash = {
        f.get("courseId"): f for f in flash if isinstance(f, dict)
    }
    course_rows = []
    for c in courses:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        course_rows.append(
            {
                "id": cid,
                "title": c.get("title"),
                "status": c.get("status"),
                "accentColor": c.get("accentColor"),
                "chatEnabled": c.get("chatEnabled"),
                "gradesSummary": by_course_grades.get(cid),
                "flashcards": by_course_flash.get(cid),
            }
        )
    return {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "user": session.get("user") if isinstance(session, dict) else None,
        "expires": session.get("expires") if isinstance(session, dict) else None,
        "courseCount": len(course_rows),
        "courses": course_rows,
        "classStanding": dash.get("classStanding") if isinstance(dash, dict) else None,
        "overallHealth": dash.get("overallHealth") if isinstance(dash, dict) else None,
    }


def course_bundle(client: AxiomClient, course_id: str) -> dict[str, Any]:
    sessions = _as_list(client.get_sessions(course_id))
    assignments = _as_list(client.get_assignments(course_id))
    quizzes = _as_list(client.get_quizzes(course_id))
    flashcards = _as_list(client.get_course_flashcards(course_id))

    submissions = []
    grades_per = []
    for a in assignments:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        aid = a["id"]
        submissions.append(
            {
                "assignmentId": aid,
                "title": a.get("title"),
                "submission": client.get_assignment_submission(aid),
            }
        )
        grades_per.append(
            {
                "assignmentId": aid,
                "title": a.get("title"),
                "grade": client.get_assignment_grade(aid),
            }
        )

    lessons = extract_lesson_markdown(
        [s for s in sessions if isinstance(s, dict)]
    )
    media = extract_media([s for s in sessions if isinstance(s, dict)])
    return {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "courseId": course_id,
        "course": client.get_course(course_id),
        "sessions": sessions,
        "assignments": assignments,
        "quizzes": quizzes,
        "grades": client.get_grades(course_id),
        "flashcards": flashcards,
        "announcements": client.get_announcements(course_id),
        "chatChannels": client.get_chat_channels(course_id),
        "submissions": submissions,
        "assignmentGrades": grades_per,
        "lessonsFlat": lessons,
        "mediaIndex": media,
        "counts": {
            "sessions": len(sessions),
            "assignments": len(assignments),
            "lessons": len(lessons),
            "quizzes": len(quizzes),
            "flashcards": len(flashcards),
        },
    }


def write_course_bundle_dir(data: dict[str, Any], directory: Path, pretty: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "bundle.json": data,
        "course.json": data["course"],
        "sessions.json": data["sessions"],
        "assignments.json": data["assignments"],
        "quizzes.json": data["quizzes"],
        "grades.json": data["grades"],
        "flashcards.json": data["flashcards"],
        "announcements.json": data["announcements"],
        "chat_channels.json": data["chatChannels"],
        "submissions.json": data["submissions"],
        "assignment_grades.json": data["assignmentGrades"],
        "lessons_flat.json": data["lessonsFlat"],
        "media_index.json": data["mediaIndex"],
    }
    for name, payload in files.items():
        (directory / name).write_text(_dump(payload, pretty), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch Axiom Learning OS student data via cookie-auth JSON APIs"
    )
    p.add_argument(
        "entity",
        nargs="?",
        choices=sorted(ENTITIES.keys()),
        help="What to fetch",
    )
    p.add_argument("--course-id", help="Course id (CUID)")
    p.add_argument("--assignment-id", help="Assignment id")
    p.add_argument("--quiz-id", help="Quiz id")
    p.add_argument("--lesson-id", help="Lesson id")
    p.add_argument("--gallery-id", help="Submission gallery id")
    p.add_argument("--channel", help="Chat channel label (G, S3, CAP, G5, DM) or id")
    p.add_argument("--query", help="Search text for search / chat-search")
    p.add_argument("--session", help="Lecture: session id, 16 / S16, title fragment, or 'all'")
    p.add_argument("--widget", help="Widget file name, e.g. cap_plan_sheet or /widgets/cap_plan_sheet.html")
    p.add_argument("--doc-id", help="Google Doc id (…/document/d/<id>/edit)")
    p.add_argument("--video", help="YouTube id or URL")
    p.add_argument("--at", help="Comma-separated timestamps: 5100, 84:05, 1:24:05, 1h24m5s")
    p.add_argument("--all-groups", action="store_true", help="capstone: also dump the other teams' group chats")
    p.add_argument("--limit", type=int, default=30, help="notifications limit")
    p.add_argument("-o", "--output", type=Path, help="Write JSON to this file")
    p.add_argument(
        "--out-dir",
        type=Path,
        help="For course-bundle/all: write split JSON files into this directory",
    )
    p.add_argument("--cookie-file", type=Path, help="File with session token")
    p.add_argument("--token", help="Raw session token")
    p.add_argument("--base-url", default=DEFAULT_BASE)
    p.add_argument("--compact", action="store_true", help="Minified JSON")
    p.add_argument(
        "--list-entities",
        action="store_true",
        help="Print entity catalog and exit",
    )
    p.add_argument(
        "--skip-auth-probe",
        action="store_true",
        help="Skip /api/auth/session probe and browser auto-refresh",
    )
    p.add_argument(
        "--no-refresh",
        action="store_true",
        help="Do not pull a fresh cookie from the browser if the session is dead",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pretty = not args.compact

    if args.list_entities:
        for name in sorted(ENTITIES):
            print(f"{name:22} {ENTITIES[name]}")
        return 0

    if not args.entity:
        build_parser().error("entity is required (or pass --list-entities)")

    try:
        if args.skip_auth_probe:
            token = resolve_token(token=args.token, cookie_file=args.cookie_file)
        else:
            token = ensure_authenticated_token(
                token=args.token,
                cookie_file=args.cookie_file,
                base_url=args.base_url,
                auto_refresh=not args.no_refresh,
            )
        client = AxiomClient(session_token=token, base_url=args.base_url)

        entity = args.entity
        cid = args.course_id

        def need_course() -> str:
            if not cid:
                raise ApiError(f"{entity} requires --course-id")
            return cid

        if entity == "session":
            return _write_out(client.get_session(), args.output, pretty)
        if entity == "me":
            return _write_out(client.get_me(), args.output, pretty)
        if entity == "courses":
            return _write_out(client.get_courses(), args.output, pretty)
        if entity == "course":
            return _write_out(client.get_course(need_course()), args.output, pretty)
        if entity == "sessions":
            return _write_out(client.get_sessions(need_course()), args.output, pretty)
        if entity == "assignments":
            return _write_out(client.get_assignments(need_course()), args.output, pretty)
        if entity == "quizzes":
            return _write_out(client.get_quizzes(need_course()), args.output, pretty)
        if entity == "quiz":
            if not args.quiz_id:
                raise ApiError("quiz requires --quiz-id")
            return _write_out(client.get_quiz(args.quiz_id), args.output, pretty)
        if entity == "grades":
            return _write_out(client.get_grades(cid), args.output, pretty)
        if entity == "grades-summary":
            return _write_out(client.get_grades_summary(), args.output, pretty)
        if entity == "submission":
            if not args.assignment_id:
                raise ApiError("submission requires --assignment-id")
            return _write_out(
                client.get_assignment_submission(args.assignment_id),
                args.output,
                pretty,
            )
        if entity == "assignment-grade":
            if not args.assignment_id:
                raise ApiError("assignment-grade requires --assignment-id")
            return _write_out(
                client.get_assignment_grade(args.assignment_id),
                args.output,
                pretty,
            )
        if entity == "flashcards":
            return _write_out(
                client.get_course_flashcards(need_course()), args.output, pretty
            )
        if entity == "dashboard-flashcards":
            return _write_out(client.get_dashboard_flashcards(), args.output, pretty)
        if entity == "dashboard-student":
            return _write_out(client.get_dashboard_student(), args.output, pretty)
        if entity == "dashboard":
            return _write_out(client.get_dashboard(), args.output, pretty)
        if entity == "notifications":
            return _write_out(
                client.get_notifications(args.limit), args.output, pretty
            )
        if entity == "announcements":
            return _write_out(
                client.get_announcements(need_course()), args.output, pretty
            )
        if entity == "chat-courses":
            return _write_out(client.get_chat_courses(), args.output, pretty)
        if entity == "chat-channels":
            return _write_out(
                client.get_chat_channels(need_course()), args.output, pretty
            )
        if entity == "peers":
            names = lab_name_map()
            if not args.query:
                return _write_out(names, args.output, pretty)
            q = args.query.casefold()
            hits = {n: l for n, l in names.items() if n == q} or {n: l for n, l in names.items() if q in n}
            num = None
            if args.session:
                m = re.fullmatch(r"[sS]?(\d+)", args.session.strip())
                num = int(m.group(1)) if m else None
            out = []
            for n, logins in hits.items():
                for login in logins:
                    out.append({"name": n, "login": login, "repos": user_repos(login, num)})
            return _write_out(out, args.output, pretty)
        if entity == "gallery-cards":
            need_course()
            sessions = [s for s in _as_list(client.get_sessions(cid)) if isinstance(s, dict)]
            wanted = {g["id"] for g in _as_list(client.get_submission_galleries(cid))}
            if args.gallery_id:
                wanted = {args.gallery_id}
            elif args.session:
                sid = resolve_session(sessions, args.session)["id"]
                wanted = {g["id"] for g in _as_list(client.get_submission_galleries(cid)) if g.get("sessionId") == sid}
                if not wanted:
                    raise ApiError(f"no Top Submissions gallery for {args.session!r}; use `peers` (GitHub) instead")
            rows = []
            for gid in sorted(wanted):
                g = client.get_submission_gallery(cid, gid)
                rows.append({"gallery": g["title"], "sessionTitle": g.get("sessionTitle"), "cards": parse_gallery(g.get("htmlContent") or "")})
            return _write_out(rows, args.output, pretty)
        if entity == "video-frame":
            if not (args.video and args.at and args.out_dir):
                raise ApiError("video-frame requires --video --at --out-dir")
            paths = video_frames(args.video, args.at.split(","), args.out_dir)
            print("\n".join(str(p) for p in paths))
            return 0
        if entity == "transcript":
            if not args.doc_id:
                raise ApiError("transcript requires --doc-id")
            text = export_doc(args.doc_id)
            if args.output:
                args.output.write_text(text, encoding="utf-8")
                print(f"wrote {args.output}", file=sys.stderr)
            else:
                sys.stdout.write(text)
            return 0
        if entity == "widget":
            if not args.widget:
                raise ApiError("widget requires --widget")
            path = args.widget if args.widget.startswith("/") else f"/widgets/{args.widget.removesuffix('.html')}.html"
            w = fetch_widget(args.base_url, path)
            if args.out_dir:
                stem = Path(path).stem
                args.out_dir.mkdir(parents=True, exist_ok=True)
                (args.out_dir / f"{stem}.html").write_text(w["html"], encoding="utf-8")
                (args.out_dir / f"{stem}.txt").write_text(w["text"], encoding="utf-8")
                (args.out_dir / f"{stem}.data.json").write_text(_dump(w["data"], pretty), encoding="utf-8")
                print(f"wrote {args.out_dir}/{stem}.*", file=sys.stderr)
                return 0
            return _write_out({"path": path, "text": w["text"], "data": w["data"]}, args.output, pretty)
        if entity == "lectures":
            sessions = [s for s in _as_list(client.get_sessions(need_course())) if isinstance(s, dict)]
            rows = lecture_index(
                sessions,
                [a for a in _as_list(client.get_assignments(cid)) if isinstance(a, dict)],
                [q for q in _as_list(client.get_quizzes(cid)) if isinstance(q, dict)],
                [c for c in _as_list(client.get_chat_channels(cid)) if isinstance(c, dict)],
            )
            return _write_out(rows, args.output, pretty)
        if entity in {"lecture", "capstone"}:
            need_course()
            if not args.out_dir:
                raise ApiError(f"{entity} requires --out-dir")
            if entity == "lecture":
                if not args.session:
                    raise ApiError("lecture requires --session")
                rows = lecture_bundle(client, cid, args.session, args.out_dir, pretty)
                for r in rows:
                    print(f"{r['session']['title'][:50]:50s} widgets={len(r['widgets'])} transcript={r['transcript']['source']} chat={len(r['chatFiles'])} errors={len(r['errors'])}", file=sys.stderr)
                return 0
            s = capstone_bundle(client, cid, args.out_dir, pretty, args.all_groups)
            print(f"wrote {args.out_dir}/ teams={list(s['myTeams'])} channels={[c['label'] for c in s['myChannels']]} errors={len(s['errors'])}", file=sys.stderr)
            return 0
        if entity == "daily-check":
            return _write_out(client.get_daily_check(), args.output, pretty)
        if entity == "invites":
            return _write_out(client.get_invites_pending(), args.output, pretty)
        if entity in {"chat-messages", "chat-dump", "chat-roster", "chat-search", "scorecard", "galleries"}:
            need_course()
        if entity == "chat-messages":
            if not args.channel:
                raise ApiError("chat-messages requires --channel")
            chan = resolve_channel(client, cid, args.channel)
            return _write_out(client.get_all_chat_messages(cid, chan["id"]), args.output, pretty)
        if entity == "chat-dump":
            if not args.out_dir:
                raise ApiError("chat-dump requires --out-dir")
            data = chat_dump(client, cid)
            write_chat_dir(data, args.out_dir, pretty)
            counts = {k: len(v) for k, v in data["messages"].items()}
            print(f"wrote {args.out_dir}/ messages={sum(counts.values())} {counts}", file=sys.stderr)
            return 0
        if entity == "chat-roster":
            return _write_out(client.get_chat_roster(cid), args.output, pretty)
        if entity in {"chat-search", "search"} and not args.query:
            raise ApiError(f"{entity} requires --query")
        if entity == "chat-search":
            chan_id = resolve_channel(client, cid, args.channel)["id"] if args.channel else None
            return _write_out(client.search_chat(cid, args.query, chan_id), args.output, pretty)
        if entity == "search":
            return _write_out(client.search(args.query), args.output, pretty)
        if entity == "calendar":
            return _write_out(client.get_calendar(cid), args.output, pretty)
        if entity == "feed":
            return _write_out(client.get_feed(cid), args.output, pretty)
        if entity == "scorecard":
            return _write_out(client.get_scorecard(cid), args.output, pretty)
        if entity == "galleries":
            if args.gallery_id:
                return _write_out(client.get_submission_gallery(cid, args.gallery_id), args.output, pretty)
            return _write_out(client.get_submission_galleries(cid), args.output, pretty)
        if entity == "lesson":
            if not args.lesson_id:
                raise ApiError("lesson requires --lesson-id")
            return _write_out(client.get_lesson(args.lesson_id), args.output, pretty)
        if entity in {"quiz-questions", "quiz-attempt"}:
            if not args.quiz_id:
                raise ApiError(f"{entity} requires --quiz-id")
            fn = client.get_quiz_questions if entity == "quiz-questions" else client.get_quiz_attempt
            return _write_out(fn(args.quiz_id), args.output, pretty)
        if entity == "notification-prefs":
            return _write_out(client.get_notification_prefs(), args.output, pretty)
        if entity == "lessons":
            sessions = _as_list(client.get_sessions(need_course()))
            data = extract_lesson_markdown(
                [s for s in sessions if isinstance(s, dict)]
            )
            return _write_out(data, args.output, pretty)
        if entity == "media":
            sessions = _as_list(client.get_sessions(need_course()))
            data = extract_media([s for s in sessions if isinstance(s, dict)])
            return _write_out(data, args.output, pretty)
        if entity == "enrolled-summary":
            return _write_out(enrolled_summary(client), args.output, pretty)
        if entity == "course-bundle":
            data = course_bundle(client, need_course())
            if args.out_dir:
                write_course_bundle_dir(data, args.out_dir, pretty)
                print(f"wrote {args.out_dir}/ counts={data['counts']}", file=sys.stderr)
                return 0
            return _write_out(data, args.output, pretty)
        if entity == "all":
            summary = enrolled_summary(client)
            root = args.out_dir or Path("out/all")
            root.mkdir(parents=True, exist_ok=True)
            (root / "enrolled_summary.json").write_text(
                _dump(summary, pretty), encoding="utf-8"
            )
            bundles_meta: dict[str, Any] = {}
            for c in summary.get("courses") or []:
                if not isinstance(c, dict) or not c.get("id"):
                    continue
                cid_i = c["id"]
                b = course_bundle(client, cid_i)
                bundles_meta[cid_i] = {"title": c.get("title"), "counts": b["counts"]}
                write_course_bundle_dir(b, root / f"course_{cid_i}", pretty)
            index = {
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
                "bundles": bundles_meta,
            }
            (root / "index.json").write_text(_dump(index, pretty), encoding="utf-8")
            print(f"wrote {root}/ courses={len(bundles_meta)}", file=sys.stderr)
            return 0

        raise ApiError(f"unknown entity: {entity}")

    except AuthError as e:
        print(f"auth error: {e}", file=sys.stderr)
        return 2
    except ApiError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

