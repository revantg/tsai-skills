#!/usr/bin/env bash
# Collect sessions + assignments for a course id (legacy narrow collector).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COURSE_ID="${1:-cmq97i5kn032208o8xu5dab4q}"
OUT_DIR="${2:-$ROOT/out/course_${COURSE_ID}}"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m tsai_skills.collect --course-id "$COURSE_ID" --out-dir "$OUT_DIR"
