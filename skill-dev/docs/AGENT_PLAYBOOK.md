# Agent playbook — expand extraction (stateless)

Read this + [AUTH.md](./AUTH.md) + [API_SURFACE.md](./API_SURFACE.md) before adding features. Do not re-open a browser unless documenting a **new** endpoint.

---

## Already solved

| Entity | How to get it |
|--------|----------------|
| Auth | Cookie `__Secure-next-auth.session-token` |
| Enrolled courses | `GET /api/courses` → `fetch courses` / `enrolled-summary` |
| Sessions / classes | `GET /api/courses/{id}/sessions` |
| Assignments list | `GET /api/assignments?courseId=` |
| Grades + summaries | `GET /api/grades`, `?view=summaries` |
| Quizzes, flashcards, dashboard, announcements | See `skill-dev/docs/API_SURFACE.md` |
| Lesson markdown | Usually `sessions[].lessons[].markdownContent` |
| Lecture video embeds | Usually `sessions[].studioVideoHtml` (parse iframe src) |
| GMeet links | `gmeetVideoHtml` or markdown content |

Working CLIs:

- `./scripts/fetch.sh <entity>` or `python3 -m tsai_skills.fetch <entity>` (preferred)
- `./skill-dev/scripts/collect-course.sh` or `python3 -m tsai_skills.collect` (sessions + assignments only)

Grok skill (canonical): `skills/axiom-learning-os`  
(`.grok/skills/axiom-learning-os` is a symlink for discovery — use skills, not an MCP server.)

---

## Playbook for a new entity (e.g. grades)

1. **Discovery (browser once)**  
   - Start Zen with Marionette + BiDi (`zen-marionette`).  
   - Grok + `firefox-devtools` MCP `--connect-existing`.  
   - Navigate to the UI that shows the entity.  
   - `list_network_requests` → note `/api/…` paths.  
   - Update `skill-dev/docs/API_SURFACE.md` with method, path, sample fields.

2. **Minimal auth check**  
   - curl with **only** session-token cookie.  
   - Confirm 200 vs 401.

3. **Code**  
   - Add method on `AxiomClient`.  
   - Optional schema validator in `schema.py`.  
   - Wire CLI flag or subcommand in `collect.py` / new module.  
   - Fixture under `skill-dev/fixtures/` + unit test without network.

4. **Verify**  
   - Live run with `AXIOM_SESSION_TOKEN`.  
   - Unauth run fails non-zero.  
   - Do not commit secrets or personal dumps.

5. **Document**  
   - One subsection in API_SURFACE + one line in README roadmap.

---

## Parsing expansion (no new API)

Many “lecture” and “markdown” needs are pure transforms:

```text
sessions.json
  → flatten lessons
  → extract YouTube IDs from studioVideoHtml
  → extract meet.google.com from markdownContent
  → write lectures_index.json
```

Prefer this before inventing endpoints.

---

## Non-negotiables

- Never hardcode live cookies in source.
- Same cookie for all Learning OS APIs.
- Ignore RSC (`?_rsc=`) and static chunk noise.
- `login.axiom.co` is a different product.

---

## Default course id

```text
cmq97i5kn032208o8xu5dab4q
```

URL: `https://axiom.theschoolofai.in/courses/cmq97i5kn032208o8xu5dab4q`
