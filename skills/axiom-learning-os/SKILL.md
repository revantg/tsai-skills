---
name: axiom-learning-os
description: >
  Pull student data from TSAI Axiom Learning OS (axiom.theschoolofai.in) via
  cookie-auth JSON APIs. Use when the user asks about a lecture/session (lesson
  markdown, embedded widgets, transcript, YouTube videos and screenshots, the
  session chat), assignments and submissions, quizzes, grades, announcements,
  course chat (read from the beginning), or the capstone: which teams the
  student is in, rotations, tasks from group chats, deadlines. Also when another
  skill needs live Axiom course state.
metadata:
  short-description: "Fetch TSAI Axiom Learning OS student data"
---

# Axiom Learning OS

Headless **fetch** of the signed-in student's Learning OS data.
Base: `https://axiom.theschoolofai.in`.

**Repo root (always):** `~/timepass/tsai-skills`
- Absolute: `/Users/revant.gupta/timepass/tsai-skills`
- Marker: directory that contains `src/tsai_skills/` and `scripts/fetch.sh`
- Do **not** search for it — `cd` there and run `./scripts/fetch.sh …`
- Skill package lives at `skills/axiom-learning-os/` inside that repo (also mirrored to `~/.claude/skills/axiom-learning-os/`; the runnable CLI is still the repo root, not the skill mirror).

**Leading idea:** treat the SPA's `/api/*` GETs as the only data plane — same cookie, same JSON the UI already uses.

## The lecture model (read this first)

Every lecture is one **session** (`session.id`); everything else hangs off that id.

| Part | Where it lives | How to get it |
|---|---|---|
| Lesson markdown | `session.lessons[].markdownContent` | `lecture` writes `lesson.md` |
| **Widgets** (often hold the critical data: plan sheets, briefings, tables) | `<iframe src="/widgets/<name>.html">` in the markdown; public static files | `lecture` saves each as `widgets/<name>.html` + `.txt` + `.data.json`. **Always read them in full**, `<script>` data included. `widget --widget <name>` for one |
| **Transcript** | Google Doc link at the end of the lesson (public export) | `lecture` writes `transcript.txt`. No doc (e.g. Capstone Lab 2)? it falls back to YouTube auto-captions → `transcript_captions.txt` |
| **Videos** (usually two) | `studioVideoHtml` = lecture recording, `gmeetVideoHtml` = live class | listed in `lecture.json`. **Take screenshots at specific moments** with `video-frame --video <id> --at 1:24:05,1:30:00 --out-dir …` (no login, needs yt-dlp + ffmpeg); use captions timestamps to pick the moments |
| **Chat** | one channel per lecture, label `S<n>`; `CAP` for capstone; team groups `G1`…`G12` | `lecture` writes `chat/S<n>.md` (full history, IST). `chat-messages --channel S16` for one channel |
| **Assignment** | `assignment.sessionId == session.id` (serial numbers match too: Session N ↔ assignment order N−1) | `lecture` writes `assignments.json` with own submission + grade |
| Quiz (sometimes) | `quiz.sessionId == session.id` | `lecture` writes `quizzes.json`; attempt + questions only if already attempted (never starts an attempt) |

One command gets all of it: `./scripts/fetch.sh lecture --course-id CID --session 16 --out-dir out/s16`
(`--session` = id, `16`/`S16`, a title fragment like `lab 2`, or `all`). `lectures` lists every session with counts.

## Capstone (when the user asks about teams, rotations, tasks, deadlines)

`./scripts/fetch.sh capstone --course-id CID --out-dir out/cap` builds the whole picture:

1. **Lectures + widgets + transcripts** for the capstone sessions (`CAP – Capstone Lab 1`, `Capstone Lab 2`). The lesson text and widgets carry context: the **plan sheet** widget (`cap_plan_sheet`: teams, leads, rosters, rotations, weekly tasks, gates, the student's pack row) and the **Lab 2 briefing** widget (week-1 results, week-2 goals per team).
2. **My teams** (`capstone.md`, `capstone.json`): core team, week-2 rotation team, week-3 rotation team, resolved from the student's row in the plan sheet, with lead, mission, milestones, the weekly tasks, the rotation task, and the rotation members.
3. **Full chat history from the beginning** for `CAP`, the student's DM, and their team groups (`chat/*.md`, times in IST). Task assignments usually appear here: the Admin's weekly brief per group (pinned or first post of the week) and the lead's task table. `admin_posts.md` collects every non-student post; `mentions.md` collects messages that name or reply to the student.

Then **read** `capstone.md`, `admin_posts.md` and each group's `.md` end to end before answering; do not rely on summaries. Re-run before answering any "what's new" question (plan sheet and chat change daily; check `planSheetUpdated`). `--all-groups` also dumps the other teams' groups.

Cross-check deadlines against who set them: TSAI/Admin dates (gates, week briefs) vs a lead's internal dates (task tables, `plan_*.md`).

GitHub work (PRs, merges, reviews) is not in Axiom: use `gh` for the lab repo.

## Other students' submissions

Axiom only returns **your own** submission (`…/submissions` is 403 for students). To read someone else's work:

1. **Top Submissions** (the "Top Submissions" tab; one gallery per lecture, but **only some lectures have one**: today S1, S2, S3). Check first with `galleries --course-id CID` (list) or `lectures`. `gallery-cards --course-id CID --session 3` parses it to rows: student **name**, submission **URL** (live Netlify/surge app), description, thumbnail. It does **not** give GitHub handles. A card count can differ from the page's own header (S3 says 85, has 92 cards); trust the cards.
2. **No gallery for that lecture** → go through GitHub. Later assignments (S9 on) are public repos, not web apps.
   - **Name → login:** every lab PR in `theschoolofai/era-v5-lab` starts with a `Name:` line, so `peers` (no args) maps ~88 names to their PR author login. Use this whenever a gallery gives only a name. A name can map to two logins (the student's own two accounts; e.g. Revant Gupta → `revantg`, `revantgupta`; course work is under `revantg`).
   - **Find the repo:** `peers --query "mahesh sv" --session 9` lists that student's public non-fork repos whose description says "Session 9" or whose name has an `s9` token. Without `--session` it lists all their repos.
   - **Read it:** `gh repo view <login>/<repo>`, `gh api repos/<login>/<repo>/contents/<path>`, or clone. Public repos only; private ones (the lab-repo forks, diagnosis packs) are not reachable.
3. Their GitHub handle can also be in their own Axiom submission (S15 team selection has a "GitHub profile" link), but that is theirs alone; use the lab PRs.

Students not in the lab PRs (waitlist, no PR yet) cannot be resolved; say so rather than guessing a login from the display name. Searching GitHub by name (`search/users`) returns look-alikes: confirm against a PR before trusting it.

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

**User pasted a cookie (browser-extension JSON export)?** Take the `__Secure-next-auth.session-token`
`value`, write it to `.secrets/session_token` **and** `src/tsai_skills/local_cookie.py`
(`SESSION_TOKEN = "…"`, mode 0600), then `./scripts/fetch.sh session --no-refresh` to prove it.
The token is a NextAuth JWE (`eyJhbGciOiJkaXIi…`), ~30-day expiry. The csrf/callback-url cookies are not needed for GETs.

## Steps

### 1. Fetch (auth is automatic)

```bash
cd ~/timepass/tsai-skills
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
| Chat channel list (G, S1…S16, CAP, G1–G12 team groups, DM) | `chat-channels` | `--course-id` |
| One channel's full history | `chat-messages` | `--course-id --channel G5` (label or id) |
| Every channel → JSON + one `.md` per channel | `chat-dump` | `--course-id --out-dir …` |
| Find a chat message | `chat-search` | `--course-id --query …` (optional `--channel`) |
| Who is in the course / online | `chat-roster` | `--course-id` |
| ⌘K global search | `search` | `--query …` |
| Calendar / upcoming | `calendar` | optional `--course-id` |
| Shared reading links | `feed` | optional `--course-id` |
| Weighted scorecard | `scorecard` | `--course-id` |
| Top Submissions | `galleries` | `--course-id` (`--gallery-id` for HTML) |
| Top Submissions as rows (name, URL) | `gallery-cards` | `--course-id` (`--session 3`/`--gallery-id`); errors with a pointer to `peers` if the lecture has none |
| Other students' GitHub logins and repos | `peers` | optional `--query NAME --session N`; needs `gh`, no Axiom login |
| One lesson | `lesson` | `--lesson-id` |
| Quiz questions / my attempt | `quiz-questions` / `quiz-attempt` | `--quiz-id` |
| All lectures with widget/transcript/video/chat/assignment/quiz counts | `lectures` | `--course-id` |
| **Everything for one lecture** (lesson, widgets, transcript, videos, chat, assignment+submission+grade, quiz) | `lecture` | `--course-id --session 16\|S16\|"lab 2"\|all --out-dir …` |
| **Capstone: my teams, rotations, plan sheet, lectures, full group chats** | `capstone` | `--course-id --out-dir …` (`--all-groups` optional) |
| One widget in full (HTML + text + parsed data) | `widget` | `--widget cap_plan_sheet [--out-dir …]` |
| Transcript text from a Google Doc id | `transcript` | `--doc-id …` |
| Screenshots from a YouTube video | `video-frame` | `--video ID\|URL --at 1:24:05,1:30:00 --out-dir …` (no login) |
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

- **Read-only.** Never call the POST/PATCH/DELETE routes (chat send/react/pin/hand, `…/chat/channels/{id}/read`, `chat/read-all`, quiz submit/autosave, assignment submit, notifications mark-read). Opening chat in the **UI** POSTs `/read` and clears unread; the CLI's GETs do not.
- Own-account data only (UI-equivalent access).
- Cookie files stay under `.secrets/` / gitignored `local_cookie.py` — never commit tokens.
- Auto-refresh only **reads** the browser cookie store; it does not automate Google OAuth.
- Capstone output holds **signed S3 download links** (plan-sheet packs/tokenizer sample) that expire, and chat dumps with other students' data. Write it under `out/` (gitignored) or the capstone notes folder, never into a git repo.
- Times in answers: **IST**. The CLI renders markdown in IST; raw JSON stays ISO UTC.
- `login.axiom.co` observability product is out of scope.
