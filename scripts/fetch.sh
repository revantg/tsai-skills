#!/usr/bin/env bash
# Repo-root shortcut for the skill's own runner.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skills/axiom-learning-os/scripts/fetch.sh" "$@"
