# Axiom Learning OS — verified API endpoints (2026-07)

Load this file when parsing fields, debugging a response, or adding a fetch entity.
Default skill path stays in `SKILL.md` steps — do not re-list this table there.

Base URL: `https://axiom.theschoolofai.in`  
Auth: `Cookie: __Secure-next-auth.session-token=<token>` only.

Live-probed against a student session. 404 paths are listed as non-endpoints.

CLI maps 1:1 via `python3 -m tsai_skills.fetch <entity>` (see `--list-entities`).

---

## Identity & enrollment

### `GET /api/auth/session`

| Auth | Status | Body |
|------|--------|------|
| Valid | 200 | `{ user: { name, email, image, id, role }, expires, loginAt }` |
| Missing | 200 | `{}` |

### `GET /api/me`

Student profile:

- `id`, `name`, `email`, `avatarUrl`, `role`
- `githubId`, `githubUsername` (may be null)
- `createdAt`, `lastLoginAt`

### `GET /api/courses`

**Enrolled courses** array. Each item:

- `id`, `title`, `description`, `accentColor`, `status` (`active`), `createdAt`, `chatEnabled`

### `GET /api/courses/{courseId}`

Same shape as a single course object from the list (detail view).

### `GET /api/dashboard`

Home shell:

- `courses[]` — includes `totalSessions`, `completedSessions` plus course fields
- `deadlines[]`
- `activity[]` — `{ id, type, title, description, timestamp }`

---

## Course content

### `GET /api/courses/{courseId}/sessions`

Primary **class/lecture** payload. Array of:

| Field | Extract |
|-------|---------|
| `id`, `title`, `order`, `status` | Session identity |
| `opensAt`, `closesAt` | Availability |
| `studioVideoHtml` | Lecture iframe HTML (parse YouTube) |
| `gmeetVideoHtml` | Live meet HTML |
| `lessons[]` | `title`, `markdownContent` (often full), `markdownUrl`, `estimatedMinutes` |
| `quizzes[]`, `assignments[]` | Nested stubs (prefer dedicated list endpoints) |

### `GET /api/assignments?courseId=`

| Field | Extract |
|-------|---------|
| `id`, `title`, `sessionId`, `courseId` | Identity |
| `descriptionMarkdown` | Full brief |
| `dueAt`, `maxPoints`, `status`, `kind` | Logistics |
| `parts[]` | `label`, `type` (e.g. `link`), `points`, `prompt` |
| `hasUserSubmission`, `submissionCount` | Progress |
| `rubricJson`, `assignmentRepoUrl` | Extra |

### `GET /api/assignments/{id}/submission`

Own submission or structured object with:

- `submittedAt`, `isLate`, `answers[]` with `answer.links[]`, `earnedPoints`
- `submittedBy: { userId, name, isMe }`

May be `null` if not submitted.

### `GET /api/assignments/{id}/grade`

- `score`, `extraPoints`, `feedback`, `gradedAt`, `isDraft`
- Nested `assignment`, `grader`
- `null` if not graded yet

### `GET /api/quizzes?courseId=`

List items:

- `id`, `title`, `sessionId`, `courseId`
- `timeLimit`, `opensAt`, `closesAt`, `maxAttempts`, `questionCount`, `order`
- `hasUserAttempt`, `attemptCount`, `_count`

### `GET /api/quizzes/{quizId}`

Metadata only (no full question bank in this response). Includes `course`, `session.status`.

### `GET /api/courses/{id}/flashcards`

Cards:

- `prompt`, `answer`, `type` (e.g. `mcq`), `contentJson` (options)
- `sessionId`, `sessionTitle`, `order`
- `myRating`, `attemptedCount`, `masteredCount`

### `GET /api/courses/{id}/announcements`

- `title`, `content`, `isPinned`, `createdAt`
- `author: { id, name, avatarUrl }`

### `GET /api/courses/{id}/chat/channels`

- `type`: `general` \| `session` \| `dm`
- `label`, `sessionTitle`, `unread`, `unreadMentions`, `canPost`, `hasMessages`

Message history is separate (`…/chat/channels/{id}/messages`) — optional expansion.

---

## Grades & progress

### `GET /api/grades`

Optional `?courseId=`. Array of grade rows:

- `score`, `extraPoints`, `feedback`, `gradedAt`
- `assignmentId` / `quizId`, nested `assignment` or `quiz`

### `GET /api/grades?view=summaries`

Used by SPA `/grades` page:

- `courseId`, `courseTitle`, `totalEarned`, `totalPossible`
- `gradedItemCount`, `overallPercentage`

### `GET /api/dashboard/student`

| Key | Contents |
|-----|----------|
| `classStanding` | `percentile`, `rank`, `totalStudents`, `averageScore`, `classAverage`, `status` |
| `overallHealth` | quiz/assignment completion, `avgQuizScore`, `pendingItems`, `weakAreaCount` |
| `scoreTrajectory[]` | assignment/quiz scores over time |
| `weakAreas[]` | quizzes with wrong question snippets |
| `actionItems[]` | todo-like items |
| `feed[]` | browse/feed cards (papers, links) |

### `GET /api/dashboard/flashcards`

Per-course: `total`, `attempted`, `unattempted`, `mastered`.

---

## Chrome / misc

| Path | Notes |
|------|-------|
| `GET /api/notifications?limit=N` | `{ items: [{ type, title, body, linkUrl, meta, readAt, createdAt }] }` |
| `GET /api/me/chat/courses` | Chat rail: `unread`, `handsUp` |
| `GET /api/daily-check` | `{ items: [] }` |
| `GET /api/invites/pending` | Array (often empty) |
| `POST /api/activity/heartbeat` | Presence; ignore for extraction |
| `POST /api/auth/_log` | NextAuth client log; ignore |

---

## Not found (do not use)

Probed 404:

- `/api/announcements?courseId=` (use course-scoped path)
- `/api/me/profile`
- `/api/leaderboard`, `/api/courses/{id}/leaderboard`
- `/api/courses/{id}/members`
- `/api/browse`, `/api/feed`, `/api/courses/{id}/feed`

---

## Parsing without new HTTP

```text
sessions.json
  → lessons[].markdownContent     full lesson text
  → studioVideoHtml               YouTube embed src
  → gmeetVideoHtml / markdown     meet.google.com links
```

CLI helpers:

```bash
PYTHONPATH=src python3 -m tsai_skills.fetch lessons --course-id CID
PYTHONPATH=src python3 -m tsai_skills.fetch media --course-id CID
```
