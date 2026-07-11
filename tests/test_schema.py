"""Contract tests on fixture JSON (no network)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tsai_collector.schema import (  # noqa: E402
    SchemaError,
    extract_lesson_markdown,
    session_looks_authenticated,
    validate_assignments,
    validate_sessions,
)


class SchemaTests(unittest.TestCase):
    def test_sessions_fixture(self) -> None:
        data = json.loads((ROOT / "fixtures" / "sessions_sample.json").read_text())
        items = validate_sessions(data)
        self.assertGreaterEqual(len(items), 1)
        for k in ("id", "title", "order", "status"):
            self.assertIn(k, items[0])

    def test_assignments_fixture(self) -> None:
        data = json.loads((ROOT / "fixtures" / "assignments_sample.json").read_text())
        items = validate_assignments(data)
        self.assertGreaterEqual(len(items), 1)
        for k in ("id", "title", "courseId"):
            self.assertIn(k, items[0])

    def test_empty_sessions_fail(self) -> None:
        with self.assertRaises(SchemaError):
            validate_sessions([])

    def test_session_probe_shapes(self) -> None:
        self.assertFalse(session_looks_authenticated({}))
        self.assertTrue(
            session_looks_authenticated({"user": {"email": "a@b.c"}, "expires": "x"})
        )

    def test_flatten_lessons(self) -> None:
        data = json.loads((ROOT / "fixtures" / "sessions_sample.json").read_text())
        rows = extract_lesson_markdown(data)
        self.assertEqual(len(rows), 1)
        self.assertIn("markdownContent", rows[0])
        self.assertIn("meet.google.com", rows[0]["markdownContent"])


if __name__ == "__main__":
    unittest.main()
