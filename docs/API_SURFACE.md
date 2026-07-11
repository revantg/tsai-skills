# API surface map (Learning OS)

Base URL: `https://axiom.theschoolofai.in`  
Auth: cookie `__Secure-next-auth.session-token` (see [AUTH.md](./AUTH.md)).

All paths below are relative to the base. Status codes assume a valid student cookie unless noted.

This map is the **expansion contract** for agents adding grades, videos, markdown extractors, etc.

---

## 1. Implemented collectors (this repo)

| Entity | Method | Path | Collector |
|--------|--------|------|-----------|
| Auth session | GET | `/api/auth/session` | `AxiomClient.get_session` |
| Course sessions | GET | `/api/courses/{courseId}/sessions` | `AxiomClient.get_sessions` |
| Assignments list | GET | `/api/assignments?courseId={courseId}` | `AxiomClient.get_assignments` |

---

## 2. Observed on course page load

When navigating to `/courses/{courseId}`, the SPA issued (order approximate):

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/auth/session` | Identity |
| GET | `/api/notifications?limit=30` | Chrome chrome |
| GET | `/api/courses` | Enrollment list |
| GET | `/api/courses/{courseId}` | Course metadata |
| GET | `/api/courses/{courseId}/sessions` | **Primary class list** |
| GET | `/api/assignments?courseId={courseId}` | **Primary assignment list** |
| GET | `/api/quizzes?courseId={courseId}` | Quizzes for course |
| GET | `/api/courses/{courseId}/flashcards` | Flashcards |
| GET | `/api/me/chat/courses` | Chat sidebar |
| GET | `/api/assignments/{id}/submission` | Per visible assignment |
| GET | `/api/assignments/{id}/grade` | Per visible assignment |
| POST | `/api/auth/_log` | NextAuth client log (ignore) |
| POST | `/api/activity/heartbeat` | Presence |

Also: many Next.js **RSC** fetches (`?_rsc=…`) and `/_next/static/*` — **ignore for data extraction**.

---

## 3. Entity → endpoint → expansion notes

### 3.1 Course

| Need | Endpoint | Notes |
|------|----------|-------|
| List enrolled courses | `GET /api/courses` | Array of course objects |
| Single course meta | `GET /api/courses/{courseId}` | Title, ids, etc. |

### 3.2 Sessions (classes / lectures)

| Need | Source | Notes |
|------|--------|-------|
| All sessions + metadata | `GET /api/courses/{id}/sessions` | **Done** |
| Lesson markdown | `sessions[].lessons[].markdownContent` | Often **fully inline** |
| Lesson remote markdown | `sessions[].lessons[].markdownUrl` | May be empty |
| Studio / lecture video | `sessions[].studioVideoHtml` | Parse iframe `src` (YouTube common) |
| GMeet live link | `sessions[].gmeetVideoHtml` **or** markdown links | Parse HTML/markdown for `meet.google.com` |
| Session status | `status`, `opensAt`, `closesAt` | |

**Agent task for “lectures”:** extend parser over existing sessions JSON — usually **no new HTTP**.

### 3.3 Assignments

| Need | Endpoint | Notes |
|------|----------|-------|
| List for course | `GET /api/assignments?courseId=` | **Done** |
| Own submission | `GET /api/assignments/{assignmentId}/submission` | Observed 200 |
| Grade for assignment | `GET /api/assignments/{assignmentId}/grade` | Observed 200 |
| Description | `descriptionMarkdown` on list item | Inline |
| Rubric / parts | `rubricJson`, `parts[]` | |

### 3.4 Grades (roadmap)

| Need | Candidate | Status |
|------|-----------|--------|
| Grades page | SPA route `/grades` hits APIs | **To verify** with network capture |
| Possible endpoints | `GET /api/grades`, `GET /api/grades?courseId=`, or only per-assignment `/grade` | Capture on `/grades` navigation |
| Dashboard student | `GET /api/dashboard/student` | Seen on dashboard load |

**Agent task:** open `/grades` under MCP/network, record exact GETs, add `get_grades` + schema.

### 3.5 Quizzes

| Need | Endpoint | Notes |
|------|----------|-------|
| List | `GET /api/quizzes?courseId=` | Observed on course page |
| Nested on session | `sessions[].quizzes` | May be partial vs full list |

### 3.6 Flashcards

| Need | Endpoint |
|------|----------|
| Course flashcards | `GET /api/courses/{id}/flashcards` |
| Dashboard flashcards | `GET /api/dashboard/flashcards` |

### 3.7 Notifications / invites / daily

| Endpoint | Notes |
|----------|-------|
| `GET /api/notifications?limit=30` | Bell icon |
| `GET /api/invites/pending` | Invites |
| `GET /api/daily-check` | Daily check-in |

### 3.8 Chat

| Endpoint | Notes |
|----------|-------|
| `GET /api/me/chat/courses` | Courses available in chat UI |

### 3.9 Static / CMS assets

Markdown and HTML may reference:

- `/uploads/canvas-import/_assets/…` — course images (cookie may or may not be required; try same-origin fetch).
- External YouTube / Telegram / GMeet URLs inside markdown or iframe HTML.

---

## 4. Response shape contracts (sessions / assignments)

### Sessions list

```text
Array<
  {
    id: string
    courseId: string
    title: string
    order: number
    opensAt: string | null
    closesAt: string | null
    status: string
    studioVideoHtml: string
    gmeetVideoHtml: string
    lessons: Array<{
      id, sessionId, title,
      markdownUrl, markdownContent, estimatedMinutes
    }>
    quizzes: Array
    assignments: Array
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

Fixture samples (anonymized / truncated) live under `fixtures/` for unit tests.

---

## 5. Edge / transport notes

- Reverse proxy: **Caddy** (`via: 1.1 Caddy`).
- Compression: `zstd` / br / gzip — standard clients handle this.
- HTTP/2 or HTTP/3 possible (`x-firefox-http3`, `alt-svc`).
- Security headers: HSTS, `X-Frame-Options: DENY`, etc. — irrelevant to API clients.

---

## 6. IDs

IDs look like CUID/CUID2-style strings (`cmq…`, `cmr…`). Always treat as opaque strings. Course id in URLs and query params must match exactly.

---

## 7. Suggested package surface for expansion

```python
class AxiomClient:
    get_session()
    get_courses()
    get_course(course_id)
    get_sessions(course_id)          # done
    get_assignments(course_id)       # done
    get_quizzes(course_id)           # TODO
    get_assignment_submission(id)    # TODO
    get_assignment_grade(id)         # TODO
    get_course_flashcards(course_id) # TODO
    get_grades(...)                  # TODO after capture
```

Parsing helpers (no HTTP):

```python
extract_youtube_urls(studioVideoHtml) -> list[str]
extract_meet_urls(html_or_md) -> list[str]
flatten_lesson_markdown(sessions) -> list[{sessionId, lessonId, title, markdown}]
```
