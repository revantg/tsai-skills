#!/usr/bin/env bash
# Fetch any Axiom Learning OS entity (see --list-entities). Self-contained: the
# tsai_skills package sits next to this script, so it runs from any install path.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${HERE}${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m tsai_skills.fetch "$@"
