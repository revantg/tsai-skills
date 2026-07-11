#!/usr/bin/env bash
# Fetch any Axiom Learning OS entity (see --list-entities).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m tsai_skills.fetch "$@"
