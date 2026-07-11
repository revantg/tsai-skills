"""HTTP client for Axiom Learning OS (cookie auth only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_BASE = "https://axiom.theschoolofai.in"
DEFAULT_UA = "tsai-skills/0.1 (+headless; https://axiom.theschoolofai.in)"


class AuthError(RuntimeError):
    """Missing, invalid, or rejected session cookie."""


class ApiError(RuntimeError):
    """Non-auth HTTP/API failure."""


@dataclass(frozen=True)
class AxiomClient:
    session_token: str
    base_url: str = DEFAULT_BASE
    timeout_sec: float = 60.0

    def _cookie_header(self) -> str:
        token = self.session_token.strip()
        if not token:
            raise AuthError("empty session cookie/token")
        if "session-token=" in token or token.lower().startswith("cookie:"):
            raw = token
            if raw.lower().startswith("cookie:"):
                raw = raw.split(":", 1)[1].strip()
            return raw
        return f"__Secure-next-auth.session-token={token}"

    def _request(self, method: str, path: str) -> tuple[int, Any]:
        url = self.base_url.rstrip("/") + path
        req = urllib.request.Request(
            url,
            method=method,
            headers={
                "Accept": "application/json",
                "Cookie": self._cookie_header(),
                "User-Agent": DEFAULT_UA,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                status = resp.getcode() or 200
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            status = e.code
        except urllib.error.URLError as e:
            raise ApiError(f"network error for {path}: {e}") from e

        if not body.strip():
            data: Any = None
        else:
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = body

        if status == 401:
            raise AuthError(
                f"Unauthorized (HTTP 401) for {path}: cookie/session invalid or missing"
            )
        if status >= 400:
            raise ApiError(f"HTTP {status} for {path}: {str(body)[:300]}")
        return status, data

    def get_session(self) -> Any:
        """GET /api/auth/session — identity probe ({} when unauthenticated)."""
        _, data = self._request("GET", "/api/auth/session")
        return data

    def get_me(self) -> Any:
        """GET /api/me — student profile."""
        _, data = self._request("GET", "/api/me")
        return data

    def get_courses(self) -> Any:
        """GET /api/courses — enrolled courses list."""
        _, data = self._request("GET", "/api/courses")
        return data

    def get_course(self, course_id: str) -> Any:
        """GET /api/courses/{courseId} — course metadata."""
        path = f"/api/courses/{urllib.parse.quote(course_id, safe='')}"
        _, data = self._request("GET", path)
        return data

    def get_sessions(self, course_id: str) -> Any:
        """GET /api/courses/{courseId}/sessions — classes + lessons/markdown/video HTML."""
        path = f"/api/courses/{urllib.parse.quote(course_id, safe='')}/sessions"
        _, data = self._request("GET", path)
        return data

    def get_assignments(self, course_id: str) -> Any:
        """GET /api/assignments?courseId= — assignment list for a course."""
        q = urllib.parse.urlencode({"courseId": course_id})
        _, data = self._request("GET", f"/api/assignments?{q}")
        return data

    def get_quizzes(self, course_id: str) -> Any:
        """GET /api/quizzes?courseId= — quiz list for a course."""
        q = urllib.parse.urlencode({"courseId": course_id})
        _, data = self._request("GET", f"/api/quizzes?{q}")
        return data

    def get_quiz(self, quiz_id: str) -> Any:
        """GET /api/quizzes/{quizId} — single quiz metadata (no question bank)."""
        path = f"/api/quizzes/{urllib.parse.quote(quiz_id, safe='')}"
        _, data = self._request("GET", path)
        return data

    def get_assignment_submission(self, assignment_id: str) -> Any:
        """GET /api/assignments/{id}/submission — own submission (or null)."""
        path = f"/api/assignments/{urllib.parse.quote(assignment_id, safe='')}/submission"
        _, data = self._request("GET", path)
        return data

    def get_assignment_grade(self, assignment_id: str) -> Any:
        """GET /api/assignments/{id}/grade — grade for one assignment (or null)."""
        path = f"/api/assignments/{urllib.parse.quote(assignment_id, safe='')}/grade"
        _, data = self._request("GET", path)
        return data

    def get_grades(self, course_id: str | None = None) -> Any:
        """GET /api/grades[?courseId=] — full grade rows (assignments + quizzes)."""
        if course_id:
            q = urllib.parse.urlencode({"courseId": course_id})
            path = f"/api/grades?{q}"
        else:
            path = "/api/grades"
        _, data = self._request("GET", path)
        return data

    def get_grades_summary(self) -> Any:
        """GET /api/grades?view=summaries — per-course totals (grades page)."""
        _, data = self._request("GET", "/api/grades?view=summaries")
        return data

    def get_course_flashcards(self, course_id: str) -> Any:
        """GET /api/courses/{id}/flashcards — all flashcards for a course."""
        path = f"/api/courses/{urllib.parse.quote(course_id, safe='')}/flashcards"
        _, data = self._request("GET", path)
        return data

    def get_dashboard_flashcards(self) -> Any:
        """GET /api/dashboard/flashcards — flashcard progress per course."""
        _, data = self._request("GET", "/api/dashboard/flashcards")
        return data

    def get_dashboard_student(self) -> Any:
        """GET /api/dashboard/student — standing, trajectory, weak areas, feed."""
        _, data = self._request("GET", "/api/dashboard/student")
        return data

    def get_dashboard(self) -> Any:
        """GET /api/dashboard — courses + deadlines + activity."""
        _, data = self._request("GET", "/api/dashboard")
        return data

    def get_notifications(self, limit: int = 30) -> Any:
        """GET /api/notifications?limit= — bell notifications."""
        q = urllib.parse.urlencode({"limit": str(limit)})
        _, data = self._request("GET", f"/api/notifications?{q}")
        return data

    def get_announcements(self, course_id: str) -> Any:
        """GET /api/courses/{id}/announcements — course announcements."""
        path = f"/api/courses/{urllib.parse.quote(course_id, safe='')}/announcements"
        _, data = self._request("GET", path)
        return data

    def get_chat_courses(self) -> Any:
        """GET /api/me/chat/courses — chat sidebar courses + unread counts."""
        _, data = self._request("GET", "/api/me/chat/courses")
        return data

    def get_chat_channels(self, course_id: str) -> Any:
        """GET /api/courses/{id}/chat/channels — chat channel list."""
        path = f"/api/courses/{urllib.parse.quote(course_id, safe='')}/chat/channels"
        _, data = self._request("GET", path)
        return data

    def get_daily_check(self) -> Any:
        """GET /api/daily-check — daily check-in items."""
        _, data = self._request("GET", "/api/daily-check")
        return data

    def get_invites_pending(self) -> Any:
        """GET /api/invites/pending — pending invites."""
        _, data = self._request("GET", "/api/invites/pending")
        return data
