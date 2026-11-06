# skill-dev

Materials for **developing and expanding** Axiom Learning OS skills and the
headless fetch toolkit — not required for day-to-day runtime fetch.

## Layout

```
skill-dev/
  docs/           # Auth, API surface, collecting notes, playbook, RE log
  fixtures/       # Anonymized JSON for contract tests
  scripts/
    collect-course.sh   # Legacy narrow collector (sessions + assignments)
  README.md       # This file
```

## Runtime vs skill-dev

| Lives at repo root (runtime) | Lives here (skill development) |
|------------------------------|----------------------------------|
| `skills/axiom-learning-os/` (SKILL.md, runner, package `scripts/tsai_skills/`) | `docs/` |
| `scripts/fetch.sh` (shortcut to the skill runner) | `fixtures/` |
| `tests/`, `out/` | `scripts/collect-course.sh` |

## Docs map

| Doc | Purpose |
|-----|---------|
| [docs/AUTH.md](docs/AUTH.md) | Cookie auth for every API call |
| [docs/API_SURFACE.md](docs/API_SURFACE.md) | Verified endpoint map |
| [docs/COLLECTING.md](docs/COLLECTING.md) | Sessions + assignments collector notes |
| [docs/AGENT_PLAYBOOK.md](docs/AGENT_PLAYBOOK.md) | Expand extraction for new entities |
| [docs/REVERSE_ENGINEERING.md](docs/REVERSE_ENGINEERING.md) | How APIs were discovered |

## Fixtures

Anonymized samples under `fixtures/` feed unit tests:

```bash
# from repo root
python3 -m unittest discover -s tests -v
```

## Legacy collector

From repo root (script resolves `ROOT` two levels up):

```bash
./skill-dev/scripts/collect-course.sh cmq97i5kn032208o8xu5dab4q
```

Prefer `./scripts/fetch.sh course-bundle` for new work.
