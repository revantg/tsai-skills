#!/usr/bin/env python3
"""Headless collector: Axiom course sessions + assignments via NextAuth cookie.

See skill-dev/docs/AUTH.md and skill-dev/docs/COLLECTING.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from tsai_skills.auth import resolve_token as resolve_token_value
from tsai_skills.client import ApiError, AuthError, AxiomClient
from tsai_skills.schema import (
    SchemaError,
    extract_lesson_markdown,
    session_looks_authenticated,
    validate_assignments,
    validate_sessions,
)

DEFAULT_COURSE = "cmq97i5kn032208o8xu5dab4q"


def resolve_token(args: argparse.Namespace) -> str:
    return resolve_token_value(token=args.token, cookie_file=args.cookie_file)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Collect Axiom Learning OS course sessions + assignments"
    )
    p.add_argument("--course-id", default=DEFAULT_COURSE, help="Course id")
    p.add_argument("-o", "--output", type=Path, help="Write combined JSON here")
    p.add_argument(
        "--out-dir",
        type=Path,
        help="Write sessions.json + assignments.json + collect.json (+ lessons_flat.json)",
    )
    p.add_argument("--cookie-file", type=Path, help="File with session token or Cookie header")
    p.add_argument("--token", help="Raw session token (prefer env/file)")
    p.add_argument("--base-url", default="https://axiom.theschoolofai.in")
    p.add_argument(
        "--skip-session-probe",
        action="store_true",
        help="Do not call /api/auth/session before collect",
    )
    p.add_argument(
        "--allow-empty",
        action="store_true",
        help="Do not fail if sessions/assignments arrays are empty",
    )
    p.add_argument(
        "--include-lessons-flat",
        action="store_true",
        default=True,
        help="Also write lessons_flat.json (default: on when --out-dir set)",
    )
    p.add_argument(
        "--no-lessons-flat",
        action="store_true",
        help="Skip lessons_flat.json",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        token = resolve_token(args)
        client = AxiomClient(session_token=token, base_url=args.base_url)

        session_info = None
        if not args.skip_session_probe:
            session_info = client.get_session()
            if not session_looks_authenticated(session_info):
                raise AuthError(
                    "/api/auth/session returned empty/unauthenticated body {}; "
                    "cookie/session invalid or expired"
                )

        sessions_raw = client.get_sessions(args.course_id)
        assignments_raw = client.get_assignments(args.course_id)

        if args.allow_empty:
            if not isinstance(sessions_raw, list) or not isinstance(assignments_raw, list):
                raise SchemaError("expected list payloads for sessions and assignments")
            sessions = sessions_raw
            assignments = assignments_raw
        else:
            sessions = validate_sessions(sessions_raw)
            assignments = validate_assignments(assignments_raw)

        lessons_flat = extract_lesson_markdown(sessions)

        payload = {
            "collectedAt": datetime.now(timezone.utc).isoformat(),
            "baseUrl": args.base_url.rstrip("/"),
            "courseId": args.course_id,
            "session": session_info,
            "sessions": sessions,
            "assignments": assignments,
            "counts": {
                "sessions": len(sessions),
                "assignments": len(assignments),
                "lessons": len(lessons_flat),
            },
        }

        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

        if args.out_dir:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            (args.out_dir / "collect.json").write_text(text, encoding="utf-8")
            (args.out_dir / "sessions.json").write_text(
                json.dumps(sessions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            (args.out_dir / "assignments.json").write_text(
                json.dumps(assignments, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            if not args.no_lessons_flat:
                (args.out_dir / "lessons_flat.json").write_text(
                    json.dumps(lessons_flat, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            print(
                f"wrote {args.out_dir}/ "
                f"(sessions={len(sessions)} assignments={len(assignments)} "
                f"lessons={len(lessons_flat)})",
                file=sys.stderr,
            )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(
                f"wrote {args.output} "
                f"(sessions={len(sessions)} assignments={len(assignments)})",
                file=sys.stderr,
            )
        if not args.output and not args.out_dir:
            sys.stdout.write(text)

        return 0
    except AuthError as e:
        print(f"auth/session/cookie error: {e}", file=sys.stderr)
        return 2
    except (SchemaError, ApiError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
