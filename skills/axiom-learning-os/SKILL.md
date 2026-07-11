---
name: axiom-learning-os
description: >
  Pull student data from TSAI Axiom Learning OS (axiom.theschoolofai.in) via
  cookie-auth JSON APIs. Use when the user asks about enrolled courses, ERA V5
  / course progress, sessions or lectures, assignments or submissions, grades
  or class standing, quizzes, flashcards, announcements, or to dump Learning
  OS data. Also when another skill needs live Axiom course state.
metadata:
  short-description: "Fetch TSAI Axiom Learning OS student data"
---

# Axiom Learning OS

Headless **fetch** of the signed-in student's Learning OS data.
Base: `https://axiom.theschoolofai.in`. Repo root = directory with `src/tsai_skills/`.

**Leading idea:** treat the SPA's `/api/*` GETs as the only data plane — same cookie, same JSON the UI already uses.

## Auth (built-in)

Cookie is resolved automatically (no manual env required for normal use):

1. `--token` / `AXIOM_SESSION_TOKEN` / `AXIOM_COOKIE_FILE` if set  
2. `.secrets/session_token`  
3. **Hardcoded fallback** in `src/tsai_skills/local_cookie.py` (gitignored) + package default  
4. On dead session: **auto-refresh** from Zen profile cookies.sqlite  
   (`~/.zen/f7zfdnyw.Default (release)`, override with `ZEN_PROFILE`)

`./scripts/fetch.sh` calls `ensure_authenticated_token()` → probes `/api/auth/session` →
if empty/`{}` or bad, pulls a fresh `__Secure-next-auth.session-token` from the browser
DB, writes `.secrets/session_token` + updates `local_cookie.py`, re-probes once.

**Done when refresh fails:** user must be logged into Axiom in Zen; then re-run.
Manual: `./scripts/export-cookie.sh`. Detail: `skill-dev/docs/AUTH.md`.

## Steps

### 1. Fetch (auth is automatic)

```bash
cd <repo-root>
./scripts/fetch.sh session          # identity probe (refreshes cookie if needed)
./scripts/fetch.sh enrolled-summary # default first real call
```

**Done when:** JSON includes a non-empty `user` (for `session`) or course data.
Exit 2 → log into https://axiom.theschoolofai.in in Zen, retry.

### 2. Resolve scope

Map the user question to the **narrowest** entity. Discover course ids from live data.

```bash
./scripts/fetch.sh --list-entities
./scripts/fetch.sh enrolled-summary
```

| Branch (user intent) | Entity | Needs |
|----------------------|--------|--------|
| What am I enrolled in / overview | `enrolled-summary` | — |
| Profile only | `me` | — |
| Classes / lectures / syllabus | `sessions` | `--course-id` |
| Lesson text | `lessons` | `--course-id` |
| YouTube / GMeet | `media` | `--course-id` |
| Assignments / due dates | `assignments` | `--course-id` |
| My upload / links | `submission` | `--assignment-id` |
| Scores / feedback | `grades` or `grades-summary` | optional `--course-id` |
| One assignment score | `assignment-grade` | `--assignment-id` |
| Rank / weak areas | `dashboard-student` | — |
| Quizzes | `quizzes` | `--course-id` |
| Flashcards | `flashcards` | `--course-id` |
| Announcements | `announcements` | `--course-id` |
| Bell feed | `notifications` | — |
| Full course dump | `course-bundle` | `--course-id --out-dir …` |
| Every enrolled course | `all` | `--out-dir …` |

**Done when:** One primary entity (and ids) is chosen. Prefer parse-over-fetch: lesson markdown and video embeds already sit on `sessions` (`lessons` / `media`).

### 3. Answer

```bash
./scripts/fetch.sh <entity> [flags]
```

**Done when:** CLI exit 0; reply uses **titles, dates, scores** (CUIDs only when needed);
no secrets written into git-tracked paths.

Field shapes: [references/api-endpoints.md](references/api-endpoints.md) · `skill-dev/docs/API_SURFACE.md`.

## Guardrails

- Own-account data only (UI-equivalent access).
- Cookie files stay under `.secrets/` / gitignored `local_cookie.py` — never commit tokens.
- Auto-refresh only **reads** the browser cookie store; it does not automate Google OAuth.
- `login.axiom.co` observability product is out of scope.
