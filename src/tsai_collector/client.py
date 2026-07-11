"""HTTP client for Axiom Learning OS (cookie auth only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_BASE = "https://axiom.theschoolofai.in"
DEFAULT_UA = "tsai-mcp-server/0.1 (+headless; https://axiom.theschoolofai.in)"


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
        _, data = self._request("GET", "/api/auth/session")
        return data

    def get_courses(self) -> Any:
        _, data = self._request("GET", "/api/courses")
        return data

    def get_course(self, course_id: str) -> Any:
        path = f"/api/courses/{urllib.parse.quote(course_id, safe='')}"
        _, data = self._request("GET", path)
        return data

    def get_sessions(self, course_id: str) -> Any:
        path = f"/api/courses/{urllib.parse.quote(course_id, safe='')}/sessions"
        _, data = self._request("GET", path)
        return data

    def get_assignments(self, course_id: str) -> Any:
        q = urllib.parse.urlencode({"courseId": course_id})
        _, data = self._request("GET", f"/api/assignments?{q}")
        return data

    def get_quizzes(self, course_id: str) -> Any:
        q = urllib.parse.urlencode({"courseId": course_id})
        _, data = self._request("GET", f"/api/quizzes?{q}")
        return data

    def get_assignment_submission(self, assignment_id: str) -> Any:
        path = f"/api/assignments/{urllib.parse.quote(assignment_id, safe='')}/submission"
        _, data = self._request("GET", path)
        return data

    def get_assignment_grade(self, assignment_id: str) -> Any:
        path = f"/api/assignments/{urllib.parse.quote(assignment_id, safe='')}/grade"
        _, data = self._request("GET", path)
        return data
