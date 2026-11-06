# Axiom Learning OS — verified API endpoints (2026-07, chat/search/etc. added 2026-10-25)

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

- `type`: `general` \| `session` \| `group` \| `dm`
- `label` (`G`, `S1`…`S16`, `CAP`, `G1`…`G12`, `DM`), `sessionId`, `sessionTitle`
- groups: `groupTeamId`, `groupName` (e.g. `05 Architecture`), `groupMembers[] {userId, name}`
- `lastReadAt`, `unread`, `unreadMentions`, `canPost`, `hasMessages`, `dmUserId`, `dmUserName`

Every enrolled student can **read** all 12 team groups; `canPost` is true only for your own groups.

### `GET /api/courses/{id}/chat/channels/{channelId}/messages[?before=<ISO createdAt>]`

Newest 50 messages, oldest first. Page back with `before=<oldest createdAt>` until a page has < 50
(the SPA does exactly this). Message:

- `id`, `userId`, `userName`, `userRole` (`student`/`admin`), `userAvatarUrl`
- `body` (markdown), `mentions[]` (user ids), `createdAt`, `editedAt`, `pinnedAt`, `pinnedBy`
- `replyTo` (`null` or `{id, userName, userRole, body}`), `reactions[] {emoji, count, mine, userIds}`

GET does not mark the channel read. The UI separately POSTs `…/read`.

### Other chat GETs

| Path | Body |
|------|------|
| `GET /api/courses/{id}/chat/roster` | `[{id, name, role, avatarUrl, online}]` (all course members, ~330) |
| `GET /api/courses/{id}/chat/search?q=[&channelId=]` | `{hits: [{messageId, channelId, channelType, channelLabel, body, userId, userName, userRole, createdAt}]}` |
| `GET /api/courses/{id}/chat/stream` | SSE (`EventSource`), one `message` event per new/edited message; not used by the CLI |

### Chat writes (UI only; never call from the skill)

`POST …/chat/channels/{ch}/messages`, `PATCH/DELETE …/messages/{m}`, `…/messages/{m}/pin`,
`…/messages/{m}/react[?emoji=]`, `…/chat/channels/{ch}/hand[?all=1]`, `POST …/chat/channels/{ch}/read`,
`POST …/chat/read-all`, `POST …/chat/heartbeat`, `POST …/chat/dm`.

### `GET /api/courses/{id}/submission-galleries[/{galleryId}]`

"Top Submissions" tab. List: `{id, sessionId, sessionTitle, title, order}`; detail adds `kind`, `htmlContent`, `criteriaJson`.

Live galleries (2026-11-07): `erav5s1topsub` (141), `erav5s2topsub` (31), `erav5s3topsub` (92 cards; header says 85). Only some lectures have one. `kind: html`, `criteriaJson` is `{}`. `htmlContent` is a full page: `<article class="card">` per student with `<div class="title"><a href="URL">NAME</a></div>` and `<div class="desc">`; thumbnails under `/uploads/era-v5-gallery-thumbnails/`. No GitHub handles and no user ids, only the display name. See `SKILL.md` "Other students' submissions" for how to get from a name to their GitHub repo.

### `GET /api/lessons/{lessonId}`

One lesson: `markdownContent`, `markdownUrl`, `estimatedMinutes`, `session {id, title, status, course}`, `progress`.

### `GET /api/quizzes/{id}/questions` · `GET /api/quizzes/{id}/attempt`

- questions: `[{id, type, content, options[], order, points, correctAnswer, explanation}]` (answers visible after the quiz is taken)
- attempt: `{attempt: {startedAt, submittedAt, score, answersJson, answers[]}, attemptCount, inProgress}`

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

### `GET /api/courses/{id}/grades?view=scorecard`

`{overallPercentage, totalEarned, totalPossible, categories: [{category, weight, average, count, totalEarned, totalPossible, items[]}]}`

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
| `GET /api/calendar[?courseId=]` | `[{id, type, title, opensAt, dueAt, courseId, courseName, courseColor, status}]` |
| `GET /api/feed[?courseId=]` | Shared links: `{linkUrl, title, description, imageUrl, siteName, createdAt, course, author}` |
| `GET /api/search?q=` | ⌘K: `{courses[], sessions[], quizzes[], assignments[], chatMessages[{channelLabel, snippet, userName}]}` |
| `GET /api/me/notification-prefs` | `{prefs: {announcement, assignment_created, quiz_created, grade_published, find_me_request, chat_mention, chat_reply}}` |
| `POST /api/activity/heartbeat` | Presence; ignore for extraction |
| `POST /api/auth/_log` | NextAuth client log; ignore |

---

## Not found (do not use)

Probed 404:

- `/api/announcements?courseId=` (use course-scoped path)
- `/api/me/profile`
- `/api/leaderboard`, `/api/courses/{id}/leaderboard`
- `/api/courses/{id}/members` (use `…/chat/roster`)
- `/api/browse`, `/api/courses/{id}/feed` (`/api/feed` does exist now)

Student gets 403 (instructor-only): `/api/courses/{id}/roster`, `…/submissions`, `…/quiz-attempts`,
`…/analytics`, `…/enrollments`, `/api/dashboard/admin`, `/api/quizzes/{id}/analytics`.

## Discovering new endpoints

Every route the SPA can call is a string literal in its JS chunks. Open any logged-in page, collect
`/_next/static/chunks/*.js` URLs (`performance.getEntriesByType('resource')`), and grep them for
`` `/api/[^`"']+ ``. That is how the 2026-10-25 additions were found; 403 marks instructor-only.

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
scripts/fetch.sh lessons --course-id CID
scripts/fetch.sh media --course-id CID
```

## Lecture parts that are not `/api` JSON

All public GETs, no cookie (`lecture` / `widget` / `transcript` / `video-frame` use them):

| What | URL | Notes |
|------|-----|-------|
| Widget | `/widgets/<name>.html` | static, self-contained; data sits in `<script>` as `const X = …`. Strict-JSON literals are parsed to `.data.json`; JS-literal ones (unquoted keys, e.g. `const T = [{n:1}]`) stay in the `.html`/`.txt` |
| Transcript | `https://docs.google.com/document/d/<id>/export?format=txt` | id from the `[Transcript](…/document/d/<id>/edit…)` link at the end of the lesson. Not all sessions have one (Capstone Lab 2 does not) → YouTube auto-captions via `yt-dlp` |
| Video | `session.studioVideoHtml` (lecture recording), `session.gmeetVideoHtml` (live class) | YouTube iframes. Stills: `yt-dlp -g` for the stream URL, then `ffmpeg -ss <sec> -i <url> -frames:v 1` |

### Linking a lecture to everything else (all via `session.id`)

- Chat: `chat/channels[].sessionId` (`type: session`, label `S<n>`; `CAP` for Capstone Lab 1; team groups `G1`…`G12` also carry the CAP `sessionId`). Capstone Lab 2 has no channel of its own.
- Assignment: `assignments[].sessionId` (all 15 do; `session.assignments[]` is empty, ignore it).
- Quiz: `quizzes[].sessionId`. `session.quizzes[]` is empty.
- Sessions with no `Session N` title (Syllabus, pre-reads, "Assignment Solution/Summary…", the two Capstone labs) have `order` 0–12 or 90+; `order` is **not** the session number. Use the title number.

### Capstone plan-sheet widget (`cap_plan_sheet`, embedded in `CAP – Capstone Lab 1`)

`const DATA = {…}` (strict JSON) has: `teams[12]` (`id`, `name`, `scope`, `mission`, `bars`, `milestones`, `weeks[4] {week, focus, students[], we[], gate, depends[], rotation[]}`), `roster {teamId: [names]}`, `leads {teamId: name}`, `rotIn {teamId: {w2: [names], w3: [names]}}`, `waitlist[]`, `packs[]` (one row per student: `student`, `coreId`, `w2Id`, `w3Id`, `pack`, `source`, `lang`, signed `url`), `tok`/`tokclean` (tokenizer-sample download links), `updated`, `links_until`.
A student's teams = their `packs` row: core = `coreId`, week-2 rotation = `w2Id`, week-3 rotation = `w3Id`. The Lab 2 briefing widget (`cap_lab2_briefing`) has `const T` (JS literal, not JSON): per team week-1 result, week-2 goal, Gate 2 evidence.
Signed URLs expire (`links_until`); the sheet is republished often, re-fetch instead of caching.

### Chat for the capstone

Every student can read all 12 team groups (`canPost` only for their own). The Admin posts each team's weekly brief in the group; leads post task tables. Page the full history with `before=` (see above); the `chat-dump`/`capstone` entities do this.
