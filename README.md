# tsai-skills

Agent skill + headless fetch toolkit for **Axiom Learning OS**
(The School of AI, `https://axiom.theschoolofai.in`).

The agent interface is the skill `axiom-learning-os` (not an MCP server): lectures,
widgets, transcripts, video stills, assignments, grades, quizzes, chat history, and the
capstone (your teams, rotations, tasks), read-only, with your own login.

## Install (any agent: Claude Code, Codex, Cursor, …)

```bash
npx skills add revantg/tsai-skills --skill axiom-learning-os -g
```

`-g` installs for your user (`~/.claude/skills/`, `~/.agents/skills/`, …); drop it to install
into the current project. Add `-a claude-code` to pick one agent, `-y` to skip prompts.
Update later with `npx skills update`.

**Needs:** `python3` ≥ 3.9 (stdlib only, nothing to `pip install`).
Optional: [`gh`](https://cli.github.com) logged in (other students' repos),
`yt-dlp` + `ffmpeg` (video screenshots, caption transcripts).

**Log in once:** open https://axiom.theschoolofai.in in **Zen or Firefox** and sign in.
The skill reads the session cookie from the browser profile on first use. Using
Chrome/Arc/Safari? Their cookie stores are encrypted, so copy the
`__Secure-next-auth.session-token` cookie value (DevTools → Application → Cookies)
and save it:

```bash
mkdir -p ~/.config/axiom-learning-os
pbpaste > ~/.config/axiom-learning-os/session_token   # or paste into the file by hand
chmod 600 ~/.config/axiom-learning-os/session_token
```

Then ask your agent things like "what's in lecture 16?", "what are my capstone tasks this
week?", "show the G5 chat since Monday".

Run it directly from the installed folder:

```bash
~/.claude/skills/axiom-learning-os/scripts/fetch.sh enrolled-summary
```

## Cookie auth & auto-refresh

All Learning OS APIs authenticate with a single NextAuth cookie:

```
Cookie: __Secure-next-auth.session-token=<token>
```

No Bearer token, no API key, no CSRF for GETs. The CLI resolves the token
in priority order and **refreshes automatically** when the session is dead:

```
1. --token / AXIOM_SESSION_TOKEN / --cookie-file / AXIOM_COOKIE_FILE   (explicit override)
2. ~/.config/axiom-learning-os/session_token                          (saved cookie)
3. newest Axiom cookie in any Zen/Firefox profile                     (then saved to 2)
        │
        ▼
   probe GET /api/auth/session
        │
        ├─ valid (has user) → proceed
        └─ empty {} / 401  → re-read the browser cookie (3), re-probe once
```

- Profiles searched: Zen and Firefox on macOS (`~/Library/Application Support/{zen,Firefox}/Profiles`),
  Linux (`~/.zen`, `~/.mozilla/firefox`), Windows (`%APPDATA%`). Pin one with
  `AXIOM_BROWSER_PROFILE=/path/to/profile`.
- The browser does **not** need to be running; `cookies.sqlite` is copied and read from disk.
- Auto-refresh **only reads** the browser cookie store; it never automates Google OAuth or stores passwords.

```bash
./scripts/fetch.sh courses --no-refresh          # fail instead of reading the browser
./scripts/fetch.sh courses --skip-auth-probe     # skip the probe entirely (fast, unsafe)
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

Same CLI as a console script after `pip install -e .`: `tsai-fetch enrolled-summary`.

### Legacy narrow collector (sessions + assignments only)

```bash
./skill-dev/scripts/collect-course.sh cmq97i5kn032208o8xu5dab4q
```

## Skills

| Path | Purpose |
|------|---------|
| [`skills/axiom-learning-os/`](skills/axiom-learning-os/) | The skill: `SKILL.md`, `references/`, and the self-contained runner `scripts/fetch.sh` + package `scripts/tsai_skills/` |
| [`.grok/skills/axiom-learning-os`](.grok/skills/) | Symlink so Grok auto-discovers the skill |

Invoke with `/axiom-learning-os` or natural language ("what courses am I enrolled in?").

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
  skills/axiom-learning-os/  # what `npx skills add` installs
    SKILL.md
    references/
    scripts/fetch.sh         # runner (works from any install path)
    scripts/tsai_skills/     # Python package (fetch / collect / client / auth)
  .grok/skills/              # symlinks → skills/* (Grok discovery)
  scripts/fetch.sh           # repo-root shortcut to the skill runner
  skill-dev/                 # docs, fixtures, legacy collect-course
  tests/
  out/                       # gitignored live dumps
```

## Example course id

- **ERA V5:** `cmq97i5kn032208o8xu5dab4q`
- Always resolve live ids via `./scripts/fetch.sh courses` if enrollment changes.

## Safety

- The cookie lives in `~/.config/axiom-learning-os/` (or your env); never commit it or personal course dumps.
- On HTTP 401 / empty session, auto-refresh kicks in (see above); if that fails, log in again in Zen/Firefox.
- Own-account data only (same access as the UI). Read-only: no POST/PATCH/DELETE routes.

## Development

```bash
git clone https://github.com/revantg/tsai-skills && cd tsai-skills
python3 -m unittest discover -s tests -v
./scripts/fetch.sh --list-entities
pip install -e .        # optional: tsai-fetch / tsai-collect console scripts
```
