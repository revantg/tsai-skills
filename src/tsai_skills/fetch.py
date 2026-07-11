#!/usr/bin/env python3
"""Fetch any verified Axiom Learning OS entity over the student cookie APIs.

Examples:
  PYTHONPATH=src python3 -m tsai_skills.fetch courses
  PYTHONPATH=src python3 -m tsai_skills.fetch sessions --course-id CID
  PYTHONPATH=src python3 -m tsai_skills.fetch enrolled-summary
  PYTHONPATH=src python3 -m tsai_skills.fetch course-bundle --course-id CID --out-dir out/c
  PYTHONPATH=src python3 -m tsai_skills.fetch all --out-dir out/all
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
from tsai_skills.client import ApiError, AuthError, AxiomClient, DEFAULT_BASE
from tsai_skills.schema import extract_lesson_markdown

YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/embed/|youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,})",
    re.I,
)
MEET_RE = re.compile(r"https?://meet\.google\.com/[a-z0-9-]+", re.I)

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
    "chat-courses": "Chat sidebar courses + unread",
    "chat-channels": "Chat channels for a course",
    "daily-check": "Daily check-in items",
    "invites": "Pending invites",
    "lessons": "Flattened lesson markdown from sessions",
    "media": "YouTube + GMeet index from sessions",
    "enrolled-summary": "Whoami + enrolled courses + standing + grades totals",
    "course-bundle": "Full dump for one course (many endpoints)",
    "all": "enrolled-summary + course-bundle for each enrolled course",
}


def _dump(data: Any, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return json.dumps(data, ensure_ascii=False) + "\n"


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
        help="Do not pull a fresh cookie from Zen if the session is dead",
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
        if entity == "daily-check":
            return _write_out(client.get_daily_check(), args.output, pretty)
        if entity == "invites":
            return _write_out(client.get_invites_pending(), args.output, pretty)
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
