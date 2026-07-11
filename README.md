# tsai-mcp-server

Headless client + knowledge base for **Axiom Learning OS** at The School of AI:

**Host:** `https://axiom.theschoolofai.in`

This repo documents how authentication works, which HTTP APIs the browser hits, how to collect **course sessions** and **assignments** without a browser, and how that knowledge was reverse-engineered (Zen Browser + Firefox DevTools MCP). It is written so a **new agent can expand** extraction to grades, lecture video embeds, lesson markdown, quizzes, submissions, etc. without rediscovering the stack.

## Quick start — collect sessions + assignments

```bash
cd ~/timepass/tsai-mcp-server

# 1) Put your NextAuth session token somewhere local (never commit)
#    Value of cookie: __Secure-next-auth.session-token
export AXIOM_SESSION_TOKEN='eyJ…'          # raw token only
# or:
# export AXIOM_COOKIE_FILE=~/timepass/tsai-mcp-server/.secrets/session_token

# 2) Collect (stdlib Python only)
python3 -m tsai_collector.collect \
  --course-id cmq97i5kn032208o8xu5dab4q \
  --out-dir out/course_cmq97i5kn032208o8xu5dab4q
```

Requires `PYTHONPATH=src` or:

```bash
cd ~/timepass/tsai-mcp-server
PYTHONPATH=src python3 -m tsai_collector.collect --course-id cmq97i5kn032208o8xu5dab4q --out-dir out/course_…
```

Helper script:

```bash
./scripts/collect_course.sh cmq97i5kn032208o8xu5dab4q
```

Outputs under `out/…/`:

| File | Contents |
|------|----------|
| `collect.json` | Combined payload + counts + session probe |
| `sessions.json` | All class sessions + nested lessons (markdown/video HTML often **inline**) |
| `assignments.json` | Course assignments (descriptions, parts, due dates) |

## Docs map (start here)

| Doc | Purpose |
|-----|---------|
| [docs/AUTH.md](docs/AUTH.md) | **How auth works** for every API call |
| [docs/COLLECTING.md](docs/COLLECTING.md) | How to collect sessions + assignments headlessly |
| [docs/API_SURFACE.md](docs/API_SURFACE.md) | Known endpoints, shapes, expansion roadmap |
| [docs/REVERSE_ENGINEERING.md](docs/REVERSE_ENGINEERING.md) | **How this was discovered** (Zen, MCP, settings) |
| [docs/AGENT_PLAYBOOK.md](docs/AGENT_PLAYBOOK.md) | Stateless runbook for agents adding new entities |

## Mental model (30 seconds)

1. Students log in with **Google** via **NextAuth** in the browser once.
2. Browser keeps an HttpOnly cookie: `__Secure-next-auth.session-token`.
3. All Learning OS JSON APIs are **same-origin** `https://axiom.theschoolofai.in/api/…` and authenticate with that cookie only (no Bearer token).
4. Headless code does the same GETs the SPA does: copy the cookie → `curl`/Python → JSON.

```
Browser (Google OAuth once)
    │
    ▼
Cookie: __Secure-next-auth.session-token
    │
    ├─ GET /api/auth/session          → identity probe
    ├─ GET /api/courses/{id}/sessions → classes + lessons (+ markdown/video HTML)
    └─ GET /api/assignments?courseId= → assignments
```

## Default course used in examples

- **Course id:** `cmq97i5kn032208o8xu5dab4q`
- **Course page:** `https://axiom.theschoolofai.in/courses/cmq97i5kn032208o8xu5dab4q`
- **ERA V5** (observed under a student account)

## Safety

- Do **not** commit `.secrets/`, live cookies, or full course dumps with personal data.
- Session cookies expire; on HTTP 401, re-export from a logged-in browser.
- This is for the student’s own account data they can already access in the UI.

## Layout

```
tsai-mcp-server/
  README.md
  docs/                 # durable knowledge (read first)
  src/tsai_collector/   # headless HTTP collector
  scripts/              # shell helpers
  fixtures/             # anonymized shape samples for tests
  tests/
  out/                  # gitignored live dumps
  .secrets/             # gitignored tokens
```

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
