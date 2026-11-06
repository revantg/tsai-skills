"""Cookie/token resolution + optional refresh from a Zen/Firefox browser profile."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from tsai_skills.client import AuthError

# Persisted token: one line, mode 0600, outside the skill folder so reinstalls keep it.
DEFAULT_COOKIE_FILE = (
    Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    / "axiom-learning-os"
    / "session_token"
)

# Firefox-family profile roots (Zen is a Firefox fork; same cookies.sqlite schema).
# Chromium browsers encrypt cookies at rest, so they are not read here.
_APPDATA = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
PROFILE_ROOTS = [
    Path.home() / "Library" / "Application Support" / "zen" / "Profiles",
    Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles",
    Path.home() / ".zen",
    Path.home() / ".mozilla" / "firefox",
    _APPDATA / "zen" / "Profiles",
    _APPDATA / "Mozilla" / "Firefox" / "Profiles",
]


def _read_token_text(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
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


def _read_cookie_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return _read_token_text(path.read_text(encoding="utf-8"))


def write_cookie_file(token: str, path: Path | None = None) -> Path:
    """Persist token for next runs (mode 0600)."""
    out = path or DEFAULT_COOKIE_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(token.strip() + "\n", encoding="utf-8")
    try:
        out.chmod(0o600)
    except OSError:
        pass
    return out


def _cookie_from_db(db_path: Path) -> tuple[int, str] | None:
    """(lastAccessed, value) of the newest Axiom session cookie in a cookies.sqlite, or None."""
    # Copy DB (+ WAL/SHM) so a locked browser profile still works.
    tmp_dir = Path(tempfile.mkdtemp(prefix="tsai-cookie-"))
    try:
        tmp_db = tmp_dir / "cookies.sqlite"
        shutil.copy2(db_path, tmp_db)
        for suffix in ("-wal", "-shm"):
            side = Path(str(db_path) + suffix)
            if side.is_file():
                shutil.copy2(side, Path(str(tmp_db) + suffix))

        con = sqlite3.connect(str(tmp_db))
        try:
            row = con.execute(
                """
                SELECT lastAccessed, value FROM moz_cookies
                WHERE name = '__Secure-next-auth.session-token'
                  AND host LIKE '%theschoolofai%'
                ORDER BY lastAccessed DESC
                LIMIT 1
                """
            ).fetchone()
        except sqlite3.Error:  # not a Firefox cookie DB / mid-migration
            return None
        finally:
            con.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    if not row or not row[1]:
        return None
    return int(row[0] or 0), str(row[1]).strip()


def browser_cookie_dbs() -> list[Path]:
    """cookies.sqlite files to search: AXIOM_BROWSER_PROFILE if set, else every Zen/Firefox profile."""
    env = os.environ.get("AXIOM_BROWSER_PROFILE", "").strip()
    if env:
        return [Path(env).expanduser() / "cookies.sqlite"]
    return sorted(p for root in PROFILE_ROOTS if root.is_dir() for p in root.glob("*/cookies.sqlite"))


def refresh_token_from_browser(*, persist: bool = True) -> str:
    """Pull the newest Axiom session cookie from any Zen/Firefox profile.

    Requires an already-logged-in browser profile (does not run Google OAuth).
    """
    dbs = browser_cookie_dbs()
    found = [c for c in (_cookie_from_db(db) for db in dbs if db.is_file()) if c]
    if not found:
        where = ", ".join(str(d.parent) for d in dbs) or "no Zen/Firefox profiles found"
        raise AuthError(
            "no Axiom session cookie in a Zen/Firefox profile "
            f"(searched: {where}). Log into https://axiom.theschoolofai.in there, "
            f"or save the __Secure-next-auth.session-token value to {DEFAULT_COOKIE_FILE}"
        )
    token = max(found)[1]
    if persist:
        write_cookie_file(token)
    return token


def resolve_token(
    token: str | None = None,
    cookie_file: str | Path | None = None,
    *,
    allow_browser: bool = False,
) -> str:
    """Resolve NextAuth session token.

    Order:
      1. explicit ``token`` / ``--token``
      2. ``AXIOM_SESSION_TOKEN``
      3. ``cookie_file`` / ``AXIOM_COOKIE_FILE``
      4. ``DEFAULT_COOKIE_FILE`` (~/.config/axiom-learning-os/session_token)
      5. if ``allow_browser``: newest cookie from a Zen/Firefox profile (then saved to 4)
    """
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
        text = _read_cookie_file(path)
        if not text:
            raise AuthError(f"cookie file empty: {path}")
        return text

    file_tok = _read_cookie_file(DEFAULT_COOKIE_FILE)
    if file_tok:
        return file_tok

    if allow_browser:
        return refresh_token_from_browser(persist=True)

    raise AuthError(
        "no session cookie: log into https://axiom.theschoolofai.in in Zen/Firefox and re-run, "
        f"or save the __Secure-next-auth.session-token value to {DEFAULT_COOKIE_FILE} "
        "(or set AXIOM_SESSION_TOKEN / AXIOM_COOKIE_FILE / --token)"
    )


def ensure_authenticated_token(
    token: str | None = None,
    cookie_file: str | Path | None = None,
    *,
    base_url: str | None = None,
    auto_refresh: bool = True,
) -> str:
    """Resolve a token and optionally refresh from the browser if the session is dead.

    Probes ``GET /api/auth/session``. On empty/expired session (or 401 on refresh path),
    pulls a new cookie from the browser and re-probes once.
    """
    from tsai_skills.client import AxiomClient
    from tsai_skills.schema import session_looks_authenticated

    def _probe(tok: str) -> bool:
        client = AxiomClient(
            session_token=tok,
            base_url=base_url or "https://axiom.theschoolofai.in",
        )
        try:
            sess = client.get_session()
        except AuthError:
            return False
        return session_looks_authenticated(sess)

    tok = resolve_token(token=token, cookie_file=cookie_file, allow_browser=auto_refresh)
    if _probe(tok):
        return tok

    if not auto_refresh:
        raise AuthError(
            "/api/auth/session unauthenticated and --no-refresh set; "
            f"save a fresh cookie to {DEFAULT_COOKIE_FILE}"
        )

    try:
        refreshed = refresh_token_from_browser(persist=True)
    except AuthError as e:
        raise AuthError(
            f"session cookie invalid/expired and browser refresh failed: {e}"
        ) from e

    if _probe(refreshed):
        return refreshed

    raise AuthError(
        "session still unauthenticated after browser cookie refresh — "
        "log into https://axiom.theschoolofai.in in Zen/Firefox, then retry"
    )
