# Authentication — Axiom Learning OS

**Scope:** `https://axiom.theschoolofai.in` only.  
**Not in scope:** `login.axiom.co` / `mcp.axiom.co` (observability product; different cookies).

---

## 1. High-level model

| Item | Value |
|------|--------|
| App | Next.js SPA (“Axiom — Learning OS”) |
| Auth library | **NextAuth** (Auth.js) |
| Interactive login | **Google OAuth** (student account) |
| API auth | **HTTP Cookie** on same origin |
| Bearer / API keys | **None** observed for student JSON APIs |
| CSRF for GETs | **Not required** |

There is no separate “API key” for students. Headless access = reuse a valid browser session cookie.

---

## 2. Cookies

### Required for data APIs

| Name | Flags (observed) | Role |
|------|------------------|------|
| `__Secure-next-auth.session-token` | `Secure`, `HttpOnly` | Encrypted session (JWE: `alg=dir`, `enc=A256GCM`). Server decrypts; client treats as opaque. |

### Optional / browser-side only

| Name | Role |
|------|------|
| `__Host-next-auth.csrf-token` | NextAuth CSRF for **mutating** auth flows (sign-in/out). **Not required** for GET `/api/courses/…` or GET `/api/assignments`. |
| `__Secure-next-auth.callback-url` | Post-login redirect hint. **Not required** for data GETs. |

### Proof of minimalism

Live probes (July 2026) showed:

- Cookie header containing **only** `__Secure-next-auth.session-token=…` → **200** on sessions + assignments.
- No cookie / garbage token → **401** `{"error":"Unauthorized"}` on those endpoints.
- Browser-only headers (`Referer`, `Sec-Fetch-*`, fancy `User-Agent`) are **not** required.

Minimal request:

```http
GET /api/courses/cmq97i5kn032208o8xu5dab4q/sessions HTTP/1.1
Host: axiom.theschoolofai.in
Accept: application/json
Cookie: __Secure-next-auth.session-token=<TOKEN>
```

---

## 3. Session probe

### `GET /api/auth/session`

| Cookie state | HTTP status | Body |
|--------------|-------------|------|
| Valid | **200** | `{"user":{…},"expires":"…","loginAt":…}` |
| Missing / invalid | **200** | `{}` (empty object — **not** 401) |

Example authenticated shape (fields, not a live secret dump):

```json
{
  "user": {
    "name": "…",
    "email": "…@gmail.com",
    "image": "https://lh3.googleusercontent.com/…",
    "id": "cmq…",
    "role": "student"
  },
  "expires": "2026-08-10T…Z",
  "loginAt": 1783759613081
}
```

**Collector policy:** treat empty `{}` as unauthenticated (exit non-zero) even though HTTP status is 200.

---

## 4. Auth behavior on data endpoints

Endpoints used for the course page (and collectors):

| Method | Path | Auth failure |
|--------|------|--------------|
| GET | `/api/courses/{courseId}/sessions` | **401** `{"error":"Unauthorized"}` |
| GET | `/api/assignments?courseId={courseId}` | **401** `{"error":"Unauthorized"}` |
| GET | `/api/courses` | 401 when unauthenticated (same pattern) |
| GET | `/api/courses/{courseId}` | 401 when unauthenticated |
| GET | `/api/quizzes?courseId=…` | same cookie |
| GET | `/api/assignments/{id}/submission` | same cookie |
| GET | `/api/assignments/{id}/grade` | same cookie |
| GET | `/api/grades` (if present) | same cookie pattern expected |
| POST | `/api/activity/heartbeat` | same cookie |
| POST | `/api/auth/_log` | NextAuth client logging; not needed headlessly |

**Rule of thumb:** every `/api/*` call under Learning OS that returns student data uses the **same** session cookie. There is no per-endpoint token.

---

## 5. How login works (interactive, reference only)

Headless collectors **do not** automate this. Documented so agents understand where the cookie comes from.

1. User opens `https://axiom.theschoolofai.in/…`.
2. Unauthenticated UI routes through NextAuth → Google OAuth.
3. On success, server sets `__Secure-next-auth.session-token`.
4. SPA polls `GET /api/auth/session` and then loads course APIs with `credentials: 'include'`.
5. Cookie is HttpOnly → **not** visible to `document.cookie`; only Network panel / cookie store / profile DB.

**Do not** store Google passwords or automate OAuth for this project unless a future goal explicitly requires it. Prefer cookie export.

---

## 6. Obtaining a cookie for headless use

### A. Firefox / Zen DevTools (easiest)

1. Log into Axiom Learning OS in Zen/Firefox.
2. Open DevTools → **Network**.
3. Click any `api/auth/session` or `api/courses/…` request.
4. Copy the `Cookie` header value for `__Secure-next-auth.session-token`, **or** Storage → Cookies → copy that cookie’s value.
5. Save to `.secrets/session_token` (one line, raw value) or export as env:

```bash
export AXIOM_SESSION_TOKEN='paste-raw-token-here'
```

### B. Profile `cookies.sqlite` (Zen)

Default Zen profile observed on Linux:

```text
~/.zen/f7zfdnyw.Default (release)/cookies.sqlite
```

```sql
SELECT name, value, host, isHttpOnly
FROM moz_cookies
WHERE host LIKE '%theschoolofai%';
```

Expected row: `name = '__Secure-next-auth.session-token'`, `host = axiom.theschoolofai.in`, `isHttpOnly = 1`.

If the DB is locked by a running browser, copy the file (+ `-wal`/`-shm` if present) elsewhere before querying, or use SQLite immutable URI.

### C. From an existing Grok + Firefox DevTools MCP session

`get_network_request` shows Cookie headers (often **truncated**). Prefer DevTools Storage or `cookies.sqlite` for a full token.

---

## 7. Expiry and refresh

- Session JSON includes `expires` (ISO timestamp).
- Responses may `Set-Cookie` a rotated session-token (rolling session).
- On collector **401** or probe `{}`: re-login in browser and re-export the cookie. Do not hardcode tokens in git.

---

## 8. Security notes for agents

- Treat tokens as **passwords** for the student account.
- Never commit `.secrets/`, raw cookies, or full `collect.json` with personal emails if the repo is shared.
- Prefer env var or ignored file path.
- `login.axiom.co` cookies (`oauth2_sid`, etc.) are **irrelevant** to Learning OS course APIs.

---

## 9. curl cheatsheet

```bash
TOKEN="…"  # raw session token

# Identity
curl -sS 'https://axiom.theschoolofai.in/api/auth/session' \
  -H 'Accept: application/json' \
  -H "Cookie: __Secure-next-auth.session-token=${TOKEN}"

# Sessions (classes)
curl -sS 'https://axiom.theschoolofai.in/api/courses/cmq97i5kn032208o8xu5dab4q/sessions' \
  -H 'Accept: application/json' \
  -H "Cookie: __Secure-next-auth.session-token=${TOKEN}"

# Assignments
curl -sS 'https://axiom.theschoolofai.in/api/assignments?courseId=cmq97i5kn032208o8xu5dab4q' \
  -H 'Accept: application/json' \
  -H "Cookie: __Secure-next-auth.session-token=${TOKEN}"
```
