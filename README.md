# tsai-skills

**Grok skills** + headless fetch toolkit for **Axiom Learning OS**
(The School of AI).

**Host:** `https://axiom.theschoolofai.in`

Agent interface is the skill `axiom-learning-os` (not an MCP server). Day-to-day
data pull is cookie + CLI; discovery used Zen + Firefox DevTools once.

## Quick start — what am I enrolled in?

```bash
cd ~/timepass/tsai-skills

# 1) Enrolled courses + standing (cookie auto-resolved — see below)
./scripts/fetch.sh enrolled-summary
# same as: PYTHONPATH=src python3 -m tsai_skills.fetch enrolled-summary
```

No env or manual cookie export is required for normal use — a hardcoded
session token is bundled (gitignored) and auto-refreshed when it expires.

## Cookie auth & auto-refresh

All Learning OS APIs authenticate with a single NextAuth cookie:

```
Cookie: __Secure-next-auth.session-token=<token>
```

No Bearer token, no API key, no CSRF for GETs. The CLI resolves the token
in priority order and **refreshes automatically** when the session is dead:

```
1. --token / AXIOM_SESSION_TOKEN / AXIOM_COOKIE_FILE   (explicit override)
2. .secrets/session_token                               (persisted cookie file)
3. src/tsai_skills/local_cookie.py                      (hardcoded fallback, gitignored)
        │
        ▼
   probe GET /api/auth/session
        │
        ├─ valid (has user) → proceed
        └─ empty {} / 401  → auto-refresh
                │
                ▼
           read Zen cookies.sqlite
           (~/.zen/f7zfdnyw.Default (release), or $ZEN_PROFILE)
                │
                ▼
           write .secrets/session_token + update local_cookie.py
                │
                ▼
           re-probe once → proceed or fail with “log into Axiom in Zen”
```

### What you need for auto-refresh

- **Zen Browser** (or Firefox) logged into `https://axiom.theschoolofai.in`.
- Default profile path: `~/.zen/f7zfdnyw.Default (release)` — override with
  `export ZEN_PROFILE=/path/to/profile`.
- The browser does **not** need to be running; `cookies.sqlite` is read from
  disk (copied to a temp dir if the profile is locked).

### Manual refresh

```bash
./scripts/export-cookie.sh          # pull from Zen → .secrets/session_token
```

### When auto-refresh fails

The session cookie in the browser is itself expired or missing. Fix:

1. Open Zen, go to `https://axiom.theschoolofai.in`, log in with Google.
2. Re-run `./scripts/fetch.sh session` (auto-refresh will pick up the new cookie).

Auto-refresh **only reads** the browser cookie store — it never automates
Google OAuth or stores passwords.

### Rotating the hardcoded cookie

`src/tsai_skills/local_cookie.py` is gitignored. After a successful refresh
(or manual export), the file is auto-updated. To set it by hand:

```bash
echo '"""Local hardcoded session cookie — gitignored, do not commit."""
SESSION_TOKEN = "eyJ…your-token…"' > src/tsai_skills/local_cookie.py
```

### Disabling auto-refresh

```bash
./scripts/fetch.sh courses --no-refresh          # fail instead of reading browser
./scripts/fetch.sh courses --skip-auth-probe     # skip probe entirely (fast, unsafe)
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

- Do not commit `.secrets/`, `local_cookie.py`, live cookies, or personal course dumps.
- On HTTP 401 / empty session, auto-refresh kicks in (see above); if that fails, re-login in Zen.
- Auto-refresh only reads the browser cookie store — no OAuth automation, no passwords stored.
- Own-account data only (same access as the UI).

## Install / tests

```bash
# optional editable install for console scripts tsai-fetch / tsai-collect
pip install -e .

PYTHONPATH=src python3 -m unittest discover -s tests -v
```
