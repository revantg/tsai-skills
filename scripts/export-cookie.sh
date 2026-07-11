#!/usr/bin/env bash
# Export __Secure-next-auth.session-token from Zen cookies.sqlite into .secrets/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="${ZEN_PROFILE:-$HOME/.zen/f7zfdnyw.Default (release)}"
DB="$PROFILE/cookies.sqlite"
OUT="${1:-$ROOT/.secrets/session_token}"

if [[ ! -f "$DB" ]]; then
  echo "cookies.sqlite not found: $DB" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"
TMP="$(mktemp)"
cp -f "$DB" "$TMP"
cp -f "${DB}-wal" "${TMP}-wal" 2>/dev/null || true
cp -f "${DB}-shm" "${TMP}-shm" 2>/dev/null || true

python3 - "$TMP" "$OUT" <<'PY'
import sqlite3, sys
from pathlib import Path
db, out = sys.argv[1], Path(sys.argv[2])
con = sqlite3.connect(db)
row = con.execute(
    """
    SELECT value FROM moz_cookies
    WHERE name = '__Secure-next-auth.session-token'
      AND host LIKE '%theschoolofai%'
    ORDER BY lastAccessed DESC LIMIT 1
    """
).fetchone()
con.close()
if not row:
    raise SystemExit("session-token cookie not found for theschoolofai.in")
out.write_text(row[0] + "\n", encoding="utf-8")
out.chmod(0o600)
print(f"wrote {out} ({len(row[0])} chars)")
PY

rm -f "$TMP" "${TMP}-wal" "${TMP}-shm"
echo "export AXIOM_COOKIE_FILE=$OUT"
