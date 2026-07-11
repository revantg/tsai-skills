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

## Steps

### 1. Unlock the session

**Do:** Resolve the NextAuth cookie, then probe identity.

```bash
cd <repo-root>
# Prefer existing token; else refresh from Zen profile
# AXIOM_SESSION_TOKEN | AXIOM_COOKIE_FILE | .secrets/session_token
./scripts/export-cookie.sh   # only if probe will fail
./scripts/fetch.sh session
```

**Done when:** JSON has a non-empty `user` object (name/email/id). Empty `{}` or exit 2 → re-export cookie and re-run this step. Auth detail only if stuck: `skill-dev/docs/AUTH.md`.

### 2. Resolve scope

**Do:** Map the user question to the **narrowest** entity. Discover course ids from live data, not memory.

```bash
./scripts/fetch.sh --list-entities
./scripts/fetch.sh enrolled-summary   # default first call
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

**Done when:** One primary entity (and ids) is chosen. Prefer parse-over-fetch: lesson markdown and video embeds already sit on `sessions` (`lessons` / `media` entities).

### 3. Fetch and answer

**Do:**

```bash
./scripts/fetch.sh <entity> [flags]
# examples:
#   ./scripts/fetch.sh sessions --course-id <CID>
#   ./scripts/fetch.sh grades-summary
#   ./scripts/fetch.sh course-bundle --course-id <CID> --out-dir out/course_<CID>
```

**Done when:**

- CLI exit 0 and JSON answers the question; and
- User-facing reply uses **titles, dates, scores** (CUIDs only when needed); and
- No secrets or personal dumps written into git-tracked paths.

Field shapes and verified paths (load only when parsing or expanding):  
[references/api-endpoints.md](references/api-endpoints.md) · repo `skill-dev/docs/API_SURFACE.md`.

## Guardrails

- Own-account data only (UI-equivalent access).
- Cookie is the credential: store under `.secrets/` or env, never commit.
- On 401 / empty session: return to step 1 (re-export), skip OAuth automation.
- `login.axiom.co` observability product is out of scope.
