# API surface map (Learning OS)

Base URL: `https://axiom.theschoolofai.in`  
Auth: cookie `__Secure-next-auth.session-token` (see [AUTH.md](./AUTH.md)).

All paths below are relative to the base. Status codes assume a valid student cookie unless noted.

**Verified live (2026-07)** with cookie-only curls + SPA network capture.  
**Agent surface:** Grok skill `.grok/skills/axiom-learning-os` + CLI
`python3 -m tsai_skills.fetch`.

---

## 1. Implemented client methods

| Entity | Method | Path | `AxiomClient` / `fetch` entity |
|--------|--------|------|--------------------------------|
| Auth session | GET | `/api/auth/session` | `get_session` / `session` |
| Profile | GET | `/api/me` | `get_me` / `me` |
| Enrolled courses | GET | `/api/courses` | `get_courses` / `courses` |
| Course meta | GET | `/api/courses/{id}` | `get_course` / `course` |
| Course sessions | GET | `/api/courses/{id}/sessions` | `get_sessions` / `sessions` |
| Assignments list | GET | `/api/assignments?courseId=` | `get_assignments` / `assignments` |
| Submission | GET | `/api/assignments/{id}/submission` | `get_assignment_submission` / `submission` |
| Assignment grade | GET | `/api/assignments/{id}/grade` | `get_assignment_grade` / `assignment-grade` |
| Grades | GET | `/api/grades` `?courseId=` | `get_grades` / `grades` |
| Grades summary | GET | `/api/grades?view=summaries` | `get_grades_summary` / `grades-summary` |
| Quizzes list | GET | `/api/quizzes?courseId=` | `get_quizzes` / `quizzes` |
| Quiz detail | GET | `/api/quizzes/{id}` | `get_quiz` / `quiz` |
| Course flashcards | GET | `/api/courses/{id}/flashcards` | `get_course_flashcards` / `flashcards` |
| Flash progress | GET | `/api/dashboard/flashcards` | `get_dashboard_flashcards` / `dashboard-flashcards` |
| Student dashboard | GET | `/api/dashboard/student` | `get_dashboard_student` / `dashboard-student` |
| Home dashboard | GET | `/api/dashboard` | `get_dashboard` / `dashboard` |
| Notifications | GET | `/api/notifications?limit=` | `get_notifications` / `notifications` |
| Announcements | GET | `/api/courses/{id}/announcements` | `get_announcements` / `announcements` |
| Chat courses | GET | `/api/me/chat/courses` | `get_chat_courses` / `chat-courses` |
| Chat channels | GET | `/api/courses/{id}/chat/channels` | `get_chat_channels` / `chat-channels` |
| Daily check | GET | `/api/daily-check` | `get_daily_check` / `daily-check` |
| Invites | GET | `/api/invites/pending` | `get_invites_pending` / `invites` |

Composite CLI entities (no extra APIs): `lessons`, `media`, `enrolled-summary`,
`course-bundle`, `all`.

---

## 2. Observed on SPA navigations

### Course page `/courses/{courseId}`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/auth/session` | Identity |
| GET | `/api/notifications?limit=30` | Chrome |
| GET | `/api/courses` | Enrollment list |
| GET | `/api/courses/{courseId}` | Course metadata |
| GET | `/api/courses/{courseId}/sessions` | **Primary class list** |
| GET | `/api/assignments?courseId={courseId}` | **Primary assignment list** |
| GET | `/api/quizzes?courseId={courseId}` | Quizzes |
| GET | `/api/courses/{courseId}/flashcards` | Flashcards |
| GET | `/api/me/chat/courses` | Chat sidebar |
| GET | `/api/assignments/{id}/submission` | Per visible assignment |
| GET | `/api/assignments/{id}/grade` | Per visible assignment |
| POST | `/api/auth/_log` | Ignore |
| POST | `/api/activity/heartbeat` | Presence |

### Grades page `/grades`

| Method | Path |
|--------|------|
| GET | `/api/grades?view=summaries` |
| GET | `/api/courses` |
| GET | `/api/auth/session` |
| GET | `/api/notifications?limit=30` |
| GET | `/api/me/chat/courses` |

### Dashboard `/`

| Method | Path |
|--------|------|
| GET | `/api/dashboard/student` |
| GET | `/api/dashboard/flashcards` |
| GET | `/api/invites/pending` |
| GET | `/api/courses` |
| GET | `/api/notifications?limit=30` |

Also: Next.js **RSC** (`?_rsc=…`) and `/_next/static/*` — **ignore**.

---

## 3. Entity → endpoint → extractable fields

### 3.1 Enrollment / course

| Need | Endpoint | Extract |
|------|----------|---------|
| List enrolled courses | `GET /api/courses` | `id`, `title`, `description`, `status`, `accentColor`, `chatEnabled` |
| Single course meta | `GET /api/courses/{id}` | same |
| Dashboard course progress | `GET /api/dashboard` | `totalSessions`, `completedSessions`, deadlines, activity |

### 3.2 Sessions (classes / lectures)

| Need | Source | Notes |
|------|--------|-------|
| All sessions + metadata | `GET /api/courses/{id}/sessions` | **Primary** |
| Lesson markdown | `sessions[].lessons[].markdownContent` | Often **fully inline** |
| Lesson remote markdown | `sessions[].lessons[].markdownUrl` | May be empty |
| Studio / lecture video | `sessions[].studioVideoHtml` | Parse iframe `src` (YouTube) |
| GMeet live link | `gmeetVideoHtml` **or** markdown | `meet.google.com` |
| Session status | `status`, `opensAt`, `closesAt` | |

**Agent task for “lectures”:** parse sessions JSON — usually **no new HTTP**.  
CLI: `fetch lessons`, `fetch media`.

### 3.3 Assignments / submissions / grades

| Need | Endpoint |
|------|----------|
| List for course | `GET /api/assignments?courseId=` |
| Own submission | `GET /api/assignments/{id}/submission` |
| Per-assignment grade | `GET /api/assignments/{id}/grade` |
| All grade rows | `GET /api/grades` or `?courseId=` |
| Course totals | `GET /api/grades?view=summaries` |

Grades row: `score`, `extraPoints`, `feedback`, `assignment`/`quiz` nest.  
Summary: `totalEarned`, `totalPossible`, `overallPercentage`, `gradedItemCount`.

### 3.4 Quizzes

| Need | Endpoint |
|------|----------|
| List | `GET /api/quizzes?courseId=` |
| Detail | `GET /api/quizzes/{id}` (metadata; not full Q-bank) |
| Nested stubs | `sessions[].quizzes` |

### 3.5 Flashcards

| Need | Endpoint |
|------|----------|
| All cards | `GET /api/courses/{id}/flashcards` |
| Progress | `GET /api/dashboard/flashcards` |

### 3.6 Dashboard analytics

`GET /api/dashboard/student`:

- `classStanding` — rank, percentile, averages
- `overallHealth` — quiz/assignment completion, avg quiz score
- `scoreTrajectory[]`, `weakAreas[]`, `actionItems[]`, `feed[]`

### 3.7 Announcements / notifications / chat

| Endpoint | Notes |
|----------|-------|
| `GET /api/courses/{id}/announcements` | Pinned + body + author |
| `GET /api/notifications?limit=30` | Bell feed |
| `GET /api/me/chat/courses` | Unread per course |
| `GET /api/courses/{id}/chat/channels` | General / session / DM channels |
| `GET /api/daily-check` | Check-in items |
| `GET /api/invites/pending` | Invites |

Chat **messages**:
`GET /api/courses/{id}/chat/channels/{channelId}/messages` (optional expansion;
captured on course page with chat open).

### 3.8 Probed 404 (do not use)

- `/api/announcements?courseId=` — use course-scoped path
- `/api/me/profile`
- `/api/leaderboard`, `/api/courses/{id}/leaderboard`
- `/api/courses/{id}/members`
- `/api/browse`, `/api/feed`, `/api/courses/{id}/feed`

---

## 4. Response shape contracts

### Sessions list

```text
Array<
  {
    id, courseId, title, order,
    opensAt, closesAt, status,
    studioVideoHtml, gmeetVideoHtml,
    lessons: Array<{ id, sessionId, title, markdownUrl, markdownContent, estimatedMinutes }>,
    quizzes: Array, assignments: Array
  }
>
```

### Assignments list

```text
Array<
  {
    id, sessionId, courseId, title,
    descriptionMarkdown, rubricJson,
    dueAt, latePolicy, maxPoints,
    assignmentRepoUrl, assignmentRepoName,
    allowResubmission, status, kind, order,
    parts: Array<{ id, assignmentId, order, label, prompt, type, points, config }>,
    hasUserSubmission?, submissionCount?, _count?
  }
>
```

### Enrolled course

```text
{ id, title, description, accentColor, status, createdAt, chatEnabled }
```

Fixture samples: `skill-dev/fixtures/`.

---

## 5. Edge / transport notes

- Reverse proxy: **Caddy** (`via: 1.1 Caddy`).
- Compression: zstd / br / gzip.
- Security headers irrelevant to API clients.
- IDs are CUID-style (`cmq…`, `cmr…`) — treat as opaque strings.

---

## 6. CLI cheatsheet

```bash
export AXIOM_COOKIE_FILE=.secrets/session_token   # or AXIOM_SESSION_TOKEN

PYTHONPATH=src python3 -m tsai_skills.fetch enrolled-summary
PYTHONPATH=src python3 -m tsai_skills.fetch courses
PYTHONPATH=src python3 -m tsai_skills.fetch sessions --course-id CID
PYTHONPATH=src python3 -m tsai_skills.fetch grades-summary
PYTHONPATH=src python3 -m tsai_skills.fetch course-bundle --course-id CID --out-dir out/c
PYTHONPATH=src python3 -m tsai_skills.fetch all --out-dir out/all
PYTHONPATH=src python3 -m tsai_skills.fetch --list-entities
```

Legacy sessions+assignments only:

```bash
PYTHONPATH=src python3 -m tsai_skills.collect --course-id CID --out-dir out/…
```
