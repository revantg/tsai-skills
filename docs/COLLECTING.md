# Collecting sessions and assignments (headless)

## Goal

For course `cmq97i5kn032208o8xu5dab4q` (or any course id), pull:

1. **All class sessions** and metadata (title, order, status, opens/closes, lessons, nested content).
2. **All assignments** for that course (title, due dates, markdown description, parts, points).

Without driving a browser during collection.

---

## Endpoints (canonical)

Base: `https://axiom.theschoolofai.in`

| Entity | Method | URL |
|--------|--------|-----|
| Auth probe | GET | `/api/auth/session` |
| Sessions | GET | `/api/courses/{courseId}/sessions` |
| Assignments | GET | `/api/assignments?courseId={courseId}` |

Auth: single cookie — see [AUTH.md](./AUTH.md).

These are exactly what the SPA requests when you open:

`https://axiom.theschoolofai.in/courses/{courseId}`

---

## What you get back

### Sessions array item (important fields)

| Field | Meaning |
|-------|---------|
| `id` | Session id (`cmq…`) |
| `courseId` | Parent course |
| `title` | Class title (e.g. “Session 2: Tokenization…”) |
| `order` | Sort order (int) |
| `opensAt` / `closesAt` | Availability window (ISO or null) |
| `status` | e.g. `available`, `completed` |
| `studioVideoHtml` | Often YouTube/iframe HTML for studio recording |
| `gmeetVideoHtml` | GMeet embed/HTML if any |
| `lessons[]` | Lesson objects |
| `lessons[].title` | Lesson title |
| `lessons[].markdownContent` | **Full lesson markdown often inline** (not only a URL) |
| `lessons[].markdownUrl` | May be empty when content is inline |
| `lessons[].estimatedMinutes` | Estimate |
| `quizzes` / `assignments` | Nested stubs (full assignment list is the separate endpoint) |

**Implication for expansion:** lecture markdown and many video links are already on the **sessions** payload. Prefer parsing `studioVideoHtml` / `markdownContent` before inventing new endpoints.

### Assignments array item (important fields)

| Field | Meaning |
|-------|---------|
| `id` | Assignment id |
| `sessionId` | Linked session |
| `courseId` | Course |
| `title` | Title |
| `descriptionMarkdown` | Full assignment text |
| `dueAt` | Deadline ISO |
| `maxPoints` | Points |
| `parts[]` | Submission parts (link uploads, prompts, points) |
| `hasUserSubmission` / `submissionCount` | Progress signals |
| `status` | e.g. `published` |
| `kind` | e.g. `individual` |

Related (not collected by default CLI, but same auth):

- `GET /api/assignments/{assignmentId}/submission`
- `GET /api/assignments/{assignmentId}/grade`

---

## Official CLI (this repo)

```bash
cd ~/timepass/tsai-mcp-server
export AXIOM_SESSION_TOKEN='…'   # or AXIOM_COOKIE_FILE

PYTHONPATH=src python3 -m tsai_collector.collect \
  --course-id cmq97i5kn032208o8xu5dab4q \
  --out-dir out/course_cmq97i5kn032208o8xu5dab4q
```

Or:

```bash
./scripts/collect_course.sh cmq97i5kn032208o8xu5dab4q
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success; non-empty sessions + assignments (unless `--allow-empty`) |
| 2 | Auth / cookie / session probe failure |
| 1 | Network or schema error |

### Env / flags

| Source | Description |
|--------|-------------|
| `AXIOM_SESSION_TOKEN` | Raw token value |
| `AXIOM_COOKIE_FILE` | File with raw token or full `Cookie:` header |
| `--token` | CLI override (avoid shell history if possible) |
| `--cookie-file` | CLI file path |
| `--course-id` | Default `cmq97i5kn032208o8xu5dab4q` |
| `--base-url` | Default `https://axiom.theschoolofai.in` |
| `--skip-session-probe` | Skip `/api/auth/session` check |
| `-o` / `--out-dir` | Output paths |

---

## Algorithm (stateless)

```
1. Resolve token from env/file (fail if missing).
2. GET /api/auth/session
   - if body is {} → fail auth
3. GET /api/courses/{id}/sessions
   - if 401 → fail auth
   - require non-empty list (by default)
4. GET /api/assignments?courseId={id}
   - same rules
5. Write JSON files
```

No browser, no Selenium at collect time. Cookie must already be valid.

---

## curl-only recipe

```bash
TOKEN=…
CID=cmq97i5kn032208o8xu5dab4q
H=(-H 'Accept: application/json' -H "Cookie: __Secure-next-auth.session-token=${TOKEN}")

curl -sS "${H[@]}" "https://axiom.theschoolofai.in/api/auth/session" | jq .
curl -sS "${H[@]}" "https://axiom.theschoolofai.in/api/courses/${CID}/sessions" -o sessions.json
curl -sS "${H[@]}" "https://axiom.theschoolofai.in/api/assignments?courseId=${CID}" -o assignments.json

jq 'length' sessions.json assignments.json
```

---

## Validating results quickly

```bash
jq '{sessions: (.sessions|length), assignments: (.assignments|length),
     firstSession: .sessions[0].title, firstAssignment: .assignments[0].title}' \
  out/course_cmq97i5kn032208o8xu5dab4q/collect.json
```

Expected shape for ERA V5 (when enrolled): **≥1 session**, **≥1 assignment**. Observed live: **7 sessions**, **2 assignments** (mid-course state).

---

## Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| exit 2, “no session cookie” | Env not set | Export token / cookie file |
| exit 2, empty session `{}` | Expired cookie | Re-login, re-export |
| exit 2 / 401 Unauthorized | Bad token | Re-export full token (not truncated) |
| Empty arrays | Wrong course id or not enrolled | Check id in browser URL |
| SSL / network errors | Offline / DNS | Retry; base URL must be exact host |

---

## What not to do

- Do not scrape HTML of the course page for sessions/assignments — JSON APIs are complete and stable for this purpose.
- Do not require BiDi/MCP for collection — MCP was only for discovery.
- Do not commit live tokens or full student payloads to git.
