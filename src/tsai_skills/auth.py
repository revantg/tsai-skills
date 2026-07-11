"""Shared cookie/token resolution for collectors and fetch CLI."""

from __future__ import annotations

import os
from pathlib import Path

from tsai_skills.client import AuthError


def resolve_token(
    token: str | None = None,
    cookie_file: str | Path | None = None,
) -> str:
    """Resolve NextAuth session token from CLI, env, or cookie file."""
    if token and token.strip():
        return token.strip()

    env_tok = os.environ.get("AXIOM_SESSION_TOKEN", "").strip()
    if env_tok:
        return env_tok

    cookie_path = cookie_file or os.environ.get("AXIOM_COOKIE_FILE", "")
    if cookie_path:
        path = Path(cookie_path).expanduser()
        if not path.is_file():
            raise AuthError(f"cookie file not found: {path}")
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise AuthError(f"cookie file empty: {path}")
        if "\n" in text and "session-token" not in text.split("\n", 1)[0]:
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("AXIOM_SESSION_TOKEN="):
                    return line.split("=", 1)[1].strip().strip("'\"")
                if "=" not in line or line.startswith("__Secure"):
                    return line
        return text

    # Default project-local secret (never commit)
    default = Path(__file__).resolve().parents[2] / ".secrets" / "session_token"
    if default.is_file():
        text = default.read_text(encoding="utf-8").strip()
        if text:
            return text

    raise AuthError(
        "no session cookie: set AXIOM_SESSION_TOKEN, AXIOM_COOKIE_FILE, "
        "--cookie-file, or --token (see skill-dev/docs/AUTH.md)"
    )
