#!/usr/bin/env bash
# Collect sessions + assignments for a course id.
# Requires AXIOM_SESSION_TOKEN or AXIOM_COOKIE_FILE (see docs/AUTH.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COURSE_ID="${1:-cmq97i5kn032208o8xu5dab4q}"
OUT_DIR="${2:-$ROOT/out/course_${COURSE_ID}}"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m tsai_collector.collect --course-id "$COURSE_ID" --out-dir "$OUT_DIR"
