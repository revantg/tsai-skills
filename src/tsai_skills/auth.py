"""Cookie/token resolution + optional refresh from Zen browser profile."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from tsai_skills.client import AuthError

# Hardcoded cookie lives in local_cookie.py (gitignored). Auto-refresh also
# rewrites that file + .secrets/session_token when the browser has a live session.
try:
    from tsai_skills.local_cookie import SESSION_TOKEN as HARDCODED_SESSION_TOKEN
except ImportError:  # pragma: no cover
    HARDCODED_SESSION_TOKEN = ""

DEFAULT_ZEN_PROFILE = Path.home() / ".zen" / "f7zfdnyw.Default (release)"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COOKIE_FILE = REPO_ROOT / ".secrets" / "session_token"


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


def extract_token_from_cookies_db(db_path: Path) -> str:
    """Read __Secure-next-auth.session-token for theschoolofai from a cookies.sqlite."""
    if not db_path.is_file():
        raise AuthError(f"cookies.sqlite not found: {db_path}")

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
                SELECT value FROM moz_cookies
                WHERE name = '__Secure-next-auth.session-token'
                  AND host LIKE '%theschoolofai%'
                ORDER BY lastAccessed DESC
                LIMIT 1
                """
            ).fetchone()
        finally:
            con.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if not row or not row[0]:
        raise AuthError(
            "session-token cookie not found in browser profile for theschoolofai.in "
            "(log into Axiom Learning OS in Zen/Firefox first)"
        )
    return str(row[0]).strip()


def zen_profile_path() -> Path:
    env = os.environ.get("ZEN_PROFILE", "").strip()
    if env:
        return Path(env).expanduser()
    return DEFAULT_ZEN_PROFILE


def refresh_token_from_browser(
    *,
    profile: Path | None = None,
    persist: bool = True,
) -> str:
    """Pull a fresh session cookie from Zen/Firefox cookies.sqlite.

    Requires an already-logged-in browser profile (does not run Google OAuth).
    """
    profile = profile or zen_profile_path()
    db = profile / "cookies.sqlite"
    token = extract_token_from_cookies_db(db)
    if persist:
        write_cookie_file(token)
        # Keep local hardcoded module in sync when present / writable.
        local_mod = Path(__file__).resolve().parent / "local_cookie.py"
        try:
            local_mod.write_text(
                '"""Local hardcoded session cookie — gitignored, do not commit."""\n\n'
                f'SESSION_TOKEN = "{token}"\n',
                encoding="utf-8",
            )
            try:
                local_mod.chmod(0o600)
            except OSError:
                pass
        except OSError:
            pass
    return token


def resolve_token(
    token: str | None = None,
    cookie_file: str | Path | None = None,
    *,
    allow_hardcoded: bool = True,
    allow_browser: bool = False,
) -> str:
    """Resolve NextAuth session token.

    Order:
      1. explicit ``token`` / ``--token``
      2. ``AXIOM_SESSION_TOKEN``
      3. ``cookie_file`` / ``AXIOM_COOKIE_FILE``
      4. ``.secrets/session_token``
      5. hardcoded fallback (local_cookie / HARDCODED_SESSION_TOKEN)
      6. if ``allow_browser``: extract from Zen cookies.sqlite
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

    if allow_hardcoded and HARDCODED_SESSION_TOKEN.strip():
        return HARDCODED_SESSION_TOKEN.strip()

    if allow_browser:
        return refresh_token_from_browser(persist=True)

    raise AuthError(
        "no session cookie: set AXIOM_SESSION_TOKEN, AXIOM_COOKIE_FILE, "
        "--cookie-file, --token, or log into Zen and re-run "
        "(auto-refresh: scripts/export-cookie.sh / refresh_token_from_browser)"
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
    pulls a new cookie from Zen and re-probes once.
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

    tok = resolve_token(token=token, cookie_file=cookie_file, allow_hardcoded=True)
    if _probe(tok):
        return tok

    if not auto_refresh:
        raise AuthError(
            "/api/auth/session unauthenticated and auto_refresh disabled; "
            "re-export cookie (scripts/export-cookie.sh)"
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
        "log into https://axiom.theschoolofai.in in Zen, then retry"
    )
