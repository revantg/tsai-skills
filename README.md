# tsai-skills

**Grok skills** + headless fetch toolkit for **Axiom Learning OS**
(The School of AI).

**Host:** `https://axiom.theschoolofai.in`

Agent interface is the skill `axiom-learning-os` (not an MCP server). Day-to-day
data pull is cookie + CLI; discovery used Zen + Firefox DevTools once.

## Quick start — what am I enrolled in?

```bash
cd ~/timepass/tsai-skills

# 1) Session cookie (never commit)
#    Cookie name: __Secure-next-auth.session-token
./scripts/export-cookie.sh
# or: export AXIOM_SESSION_TOKEN='eyJ…'

# 2) Enrolled courses + standing
./scripts/fetch.sh enrolled-summary
# same as: PYTHONPATH=src python3 -m tsai_skills.fetch enrolled-summary
```

## Fetch any entity

```bash
./scripts/fetch.sh --list-entities

./scripts/fetch.sh courses
./scripts/fetch.sh sessions --course-id cmq97i5kn032208o8xu5dab4q
./scripts/fetch.sh grades-summary
./scripts/fetch.sh lessons --course-id cmq97i5kn032208o8xu5dab4q
./scripts/fetch.sh media --course-id cmq97i5kn032208o8xu5dab4q

./scripts/fetch.sh course-bundle \
  --course-id cmq97i5kn032208o8xu5dab4q \
  --out-dir out/course_cmq97i5kn032208o8xu5dab4q

./scripts/fetch.sh all --out-dir out/all
```

Default module entry is fetch:

```bash
PYTHONPATH=src python3 -m tsai_skills enrolled-summary
```

### Legacy narrow collector (sessions + assignments only)

```bash
./skill-dev/scripts/collect-course.sh cmq97i5kn032208o8xu5dab4q
```

## Skills

| Path | Purpose |
|------|---------|
| [`skills/axiom-learning-os/`](skills/axiom-learning-os/) | Canonical skill (auth → scope → fetch) |
| [`.grok/skills/axiom-learning-os`](.grok/skills/) | Symlink so Grok auto-discovers the skill |
| `skills/…/references/api-endpoints.md` | Field-level API catalog |

Invoke with `/axiom-learning-os` or natural language (“what courses am I enrolled in?”).

## Docs (skill development)

Full map: [`skill-dev/`](skill-dev/).

| Doc | Purpose |
|-----|---------|
| [skill-dev/docs/AUTH.md](skill-dev/docs/AUTH.md) | Cookie auth for every API call |
| [skill-dev/docs/API_SURFACE.md](skill-dev/docs/API_SURFACE.md) | Verified endpoint map |
| [skill-dev/docs/COLLECTING.md](skill-dev/docs/COLLECTING.md) | Sessions + assignments collector notes |
| [skill-dev/docs/AGENT_PLAYBOOK.md](skill-dev/docs/AGENT_PLAYBOOK.md) | Expand extraction for new entities |
| [skill-dev/docs/REVERSE_ENGINEERING.md](skill-dev/docs/REVERSE_ENGINEERING.md) | How APIs were discovered |

## Mental model

1. Log in once with **Google** via **NextAuth** in the browser.
2. Reuse cookie `__Secure-next-auth.session-token` for same-origin `/api/*` GETs.
3. No Bearer token; CSRF not required for GETs.

```
Cookie: __Secure-next-auth.session-token
    ├─ /api/auth/session
    ├─ /api/courses
    ├─ /api/courses/{id}/sessions     (+ lesson markdown, video HTML)
    ├─ /api/assignments?courseId=
    ├─ /api/grades?view=summaries
    └─ /api/dashboard/student
```

## Layout

```
tsai-skills/
  skills/                    # source of truth for Grok skills
    axiom-learning-os/
  .grok/skills/              # symlinks → skills/* (Grok discovery)
  src/tsai_skills/           # Python package (fetch / collect / client)
  scripts/                   # export-cookie, fetch (runtime)
  skill-dev/                 # docs, fixtures, legacy collect-course
    docs/
    fixtures/                # anonymized JSON for tests
    scripts/collect-course.sh
  tests/
  out/                       # gitignored live dumps
  .secrets/                  # gitignored tokens
```

## Example course id

- **ERA V5:** `cmq97i5kn032208o8xu5dab4q`
- Always resolve live ids via `./scripts/fetch.sh courses` if enrollment changes.

## Safety

- Do not commit `.secrets/`, live cookies, or personal course dumps.
- On HTTP 401, re-export the cookie.
- Own-account data only (same access as the UI).

## Install / tests

```bash
# optional editable install for console scripts tsai-fetch / tsai-collect
pip install -e .

PYTHONPATH=src python3 -m unittest discover -s tests -v
```
