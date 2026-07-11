"""Pure shape checks for Axiom course JSON (no network)."""

from __future__ import annotations

from typing import Any


class SchemaError(ValueError):
    """Response JSON does not match expected shape."""


def _require_keys(obj: dict[str, Any], keys: list[str], label: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise SchemaError(f"{label} missing keys: {missing}")


def validate_session_item(item: Any, index: int = 0) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SchemaError(f"session[{index}] must be object, got {type(item).__name__}")
    _require_keys(item, ["id", "title", "order", "status"], f"session[{index}]")
    return item


def validate_sessions(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise SchemaError(f"sessions payload must be list, got {type(payload).__name__}")
    if len(payload) < 1:
        raise SchemaError("sessions list is empty")
    return [validate_session_item(x, i) for i, x in enumerate(payload)]


def validate_assignment_item(item: Any, index: int = 0) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SchemaError(f"assignment[{index}] must be object, got {type(item).__name__}")
    _require_keys(item, ["id", "title", "courseId"], f"assignment[{index}]")
    return item


def validate_assignments(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise SchemaError(f"assignments payload must be list, got {type(payload).__name__}")
    if len(payload) < 1:
        raise SchemaError("assignments list is empty")
    return [validate_assignment_item(x, i) for i, x in enumerate(payload)]


def session_looks_authenticated(payload: Any) -> bool:
    """NextAuth: valid session is object with user; missing auth is {}."""
    return isinstance(payload, dict) and isinstance(payload.get("user"), dict)


def extract_lesson_markdown(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten inline lesson markdown for downstream lecture/content pipelines."""
    rows: list[dict[str, Any]] = []
    for s in sessions:
        for lesson in s.get("lessons") or []:
            if not isinstance(lesson, dict):
                continue
            rows.append(
                {
                    "sessionId": s.get("id"),
                    "sessionTitle": s.get("title"),
                    "sessionOrder": s.get("order"),
                    "lessonId": lesson.get("id"),
                    "lessonTitle": lesson.get("title"),
                    "markdownContent": lesson.get("markdownContent") or "",
                    "markdownUrl": lesson.get("markdownUrl") or "",
                    "studioVideoHtml": s.get("studioVideoHtml") or "",
                    "gmeetVideoHtml": s.get("gmeetVideoHtml") or "",
                }
            )
    return rows
