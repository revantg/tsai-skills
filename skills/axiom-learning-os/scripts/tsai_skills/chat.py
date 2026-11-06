"""Chat channels and full message history (read-only), rendered with IST times."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from tsai_skills.client import ApiError, AxiomClient

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def dump_json(data: Any, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return json.dumps(data, ensure_ascii=False) + "\n"


def ist(value: Any) -> str:
    """ISO timestamp (UTC or offset) → 'Sat 31 Oct 2026, 08:30 IST'. Unparseable → as is."""
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(IST).strftime("%a %d %b %Y, %H:%M IST")


def list_channels(client: AxiomClient, course_id: str) -> list[dict[str, Any]]:
    payload = client.get_chat_channels(course_id)
    return [c for c in payload if isinstance(c, dict)] if isinstance(payload, list) else []


def resolve_channel(client: AxiomClient, course_id: str, ref: str) -> dict[str, Any]:
    """Match a channel by label (G, S3, CAP, G5, DM) or id, case-insensitive."""
    for c in list_channels(client, course_id):
        if ref.lower() in (str(c.get("label")).lower(), str(c.get("id")).lower()):
            return c
    raise ApiError(f"no chat channel matching {ref!r} (see chat-channels)")


def chat_dump(
    client: AxiomClient,
    course_id: str,
    keep: Callable[[dict[str, Any]], bool] | None = None,
    roster: bool = True,
) -> dict[str, Any]:
    """Full history of every channel (or those passing ``keep``), oldest first."""
    channels = [c for c in list_channels(client, course_id) if keep is None or keep(c)]
    data: dict[str, Any] = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "courseId": course_id,
        "channels": channels,
        "messages": {c["label"]: client.get_all_chat_messages(course_id, c["id"]) for c in channels},
    }
    if roster:
        data["roster"] = client.get_chat_roster(course_id)
    return data


def message_md(m: dict[str, Any]) -> str:
    head = f"**{m.get('userName')}** · {m.get('userRole')} · {ist(m.get('createdAt'))}"
    if m.get("pinnedAt"):
        head += " · pinned"
    if m.get("editedAt"):
        head += " (edited)"
    reply = m.get("replyTo")
    if isinstance(reply, dict):
        snippet = str(reply.get("body") or "")[:120].replace("\n", " ")
        head += f"\n> replying to {reply.get('userName')}: {snippet}"
    reactions = " ".join(f"{r.get('emoji')}×{r.get('count')}" for r in m.get("reactions") or [])
    return head + f"\n\n{m.get('body')}" + (f"\n\n_reactions: {reactions}_" if reactions else "")


def write_chat_dir(data: dict[str, Any], directory: Path, pretty: bool = True) -> None:
    """chat_raw.json (+ roster.json) + <label>.md per non-empty channel."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "chat_raw.json").write_text(dump_json(data, pretty), encoding="utf-8")
    if "roster" in data:
        (directory / "roster.json").write_text(dump_json(data["roster"], pretty), encoding="utf-8")
    for c in data["channels"]:
        msgs = data["messages"].get(c["label"]) or []
        if not msgs:
            continue
        title = c.get("groupName") or c.get("sessionTitle") or c.get("dmUserName") or c["type"]
        head = (
            f"# Chat {c['label']}: {title}\n\n"
            f"Channel `{c['id']}` · type `{c['type']}` · {len(msgs)} messages · "
            f"fetched {ist(data['fetchedAt'])} · all times IST\n"
        )
        members = [str(g.get("name")) for g in c.get("groupMembers") or [] if isinstance(g, dict)]
        if members:
            head += f"\nMembers ({len(members)}): {', '.join(members)}\n"
        body = "\n\n---\n\n".join(message_md(m) for m in msgs)
        (directory / f"{c['label']}.md").write_text(f"{head}\n---\n\n{body}\n", encoding="utf-8")
