#!/usr/bin/env bash
# Run from skill path: skills/axiom-learning-os/scripts → repo root is ../..
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m tsai_skills.fetch "$@"
