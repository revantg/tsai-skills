# How this knowledge was collected (reverse engineering log)

This document is **stateless context** for future agents: tools, settings, commands, and method used to reverse-engineer Axiom Learning OS. Reproduce or extend discovery without re-deriving the stack from scratch.

---

## 1. Objective (original)

Understand how to pull course data **without a browser UI** at collect time, especially:

- Sessions (classes) + metadata for  
  `https://axiom.theschoolofai.in/courses/cmq97i5kn032208o8xu5dab4q`
- Assignments for the same course
- Auth model for each request

Later expansion targets: grades, lecture videos, lesson markdown, quizzes, submissions.

---

## 2. Stack used for discovery

| Component | Role |
|-----------|------|
| **Zen Browser** | Firefox-based browser with real student cookies (Google login already present) |
| **Mozilla Firefox DevTools MCP** | `@mozilla/firefox-devtools-mcp` — attach to Zen, list pages, navigate, list/get network requests, evaluate JS |
| **Grok CLI** | MCP host; tools exposed as `firefox-devtools__*` |
| **curl / Python urllib** | Validate that cookie-only HTTP works outside the browser |
| **SQLite** on Zen profile | Extract HttpOnly session cookie when needed |

Browser automation was used for **discovery only**. The shipping collector is pure HTTP.

---

## 3. Environment specifics (Linux, this machine)

### 3.1 Zen install

| Item | Path / value |
|------|----------------|
| Launcher | `~/.local/bin/zen` → tarball binary |
| Binary | `/home/rev/.tarball-installations/zen/zen` |
| Version (observed) | Zen **1.21.6b** (Firefox/Gecko family; UA reported as Firefox/152 in requests) |
| Profile (release, used) | `~/.zen/f7zfdnyw.Default (release)` |
| `profiles.ini` | `~/.zen/profiles.ini` — install default locked to `f7zfdnyw.Default (release)` |

### 3.2 Why Marionette + Remote Debugging both matter

| Flag / port | Purpose |
|-------------|---------|
| `--marionette` → port **2828** | Attach control (tabs, navigate, DOM) via geckodriver `--connect-existing` |
| `--remote-debugging-port` → **9222** | WebDriver **BiDi** / Remote Agent — **required for network request capture** |

**Important finding:**  
`--connect-existing` with **only** Marionette can list tabs and snapshots, but:

```text
list_network_requests → Error: Network events not available
(Firefox Remote Agent not running — start with --remote-debugging-port)
```

With both flags, BiDi subscribes to `network.*` events and `list_network_requests` / `get_network_request` work.

Log line when healthy:

```text
Marionette listening on port 2828
WebDriver BiDi listening on ws://127.0.0.1:9222
```

### 3.3 Helper script used

`~/.local/bin/zen-marionette` restarts Zen with:

```bash
/home/rev/.tarball-installations/zen/zen \
  --marionette \
  --remote-debugging-port 9222 \
  --profile "/home/rev/.zen/f7zfdnyw.Default (release)"
```

Commands:

```bash
zen-marionette           # restart ready for MCP
zen-marionette --status  # check PIDs + ports 2828 + 9222
```

Security: leave Marionette/RDP on only while automating; they alter `navigator.webdriver` and open localhost control ports.

### 3.4 geckodriver

MCP’s Selenium stack needs `geckodriver` on `PATH`. Installed to:

```text
~/.local/bin/geckodriver
```

### 3.5 Firefox DevTools MCP (npm)

| Item | Value |
|------|--------|
| Package | `@mozilla/firefox-devtools-mcp` (e.g. v0.9.12) |
| Global install (this host) | under mise Node `25.2.1` |
| Entry | `…/node_modules/@mozilla/firefox-devtools-mcp/dist/index.js` |

### 3.6 Grok CLI MCP config

File: `~/.grok/config.toml`

```toml
[mcp_servers.firefox-devtools]
command = "/home/rev/.local/share/mise/installs/node/25.2.1/bin/node"
args = [
  "/home/rev/.local/share/mise/installs/node/25.2.1/lib/node_modules/@mozilla/firefox-devtools-mcp/dist/index.js",
  "--connect-existing",
  "--marionette-port", "2828",
  "--firefox-path", "/home/rev/.tarball-installations/zen/zen",
  "--enable-script",
  "--log-file", "/home/rev/.grok/logs/mcp/firefox-devtools.stderr.log",
]
startup_timeout_sec = 90
tool_timeout_sec = 120
enabled = true

[mcp_servers.firefox-devtools.env]
PATH = "/home/rev/.local/bin:/home/rev/.local/share/mise/installs/node/25.2.1/bin:/usr/local/bin:/usr/bin:/bin"
HOME = "/home/rev"
```

Notes:

- **`--connect-existing`**: attach to already-running Zen with real cookies/tabs (do not use a throwaway MCP profile if you need student login).
- **`--enable-script`**: allows `evaluate_script` (fetch from page context, inspect session JSON).
- MCP servers load at **Grok session start** — restart Grok after config changes.
- Doctor: `grok mcp doctor firefox-devtools` (expect handshake OK, ~39 tools).

### 3.7 Profile-path pitfall (do not use for real cookies)

If MCP **launches** Firefox with `--profile-path` pointing at a real profile directory, the package **creates a nested** `firefox_devtools_mcp_profile` and does **not** use your cookies. For real sessions, always **attach** (`connect-existing`) to a user-started Zen, or pass profile carefully via launch args knowing this isolation behavior.

---

## 4. Discovery procedure (repeatable)

### Step A — Start Zen ready for network capture

```bash
zen-marionette --status
# or zen-marionette
```

Confirm:

- Marionette `127.0.0.1:2828`
- BiDi `127.0.0.1:9222`

### Step B — Start Grok with firefox-devtools MCP connected

In a new Grok session, tools include e.g.:

- `firefox-devtools__list_pages`
- `firefox-devtools__select_page`
- `firefox-devtools__navigate_page`
- `firefox-devtools__list_network_requests`
- `firefox-devtools__get_network_request`
- `firefox-devtools__evaluate_script`
- `firefox-devtools__take_snapshot`

### Step C — Navigate to the course

```
navigate_page → https://axiom.theschoolofai.in/courses/cmq97i5kn032208o8xu5dab4q
```

Or select an existing “Axiom — Learning OS” tab.

### Step D — Filter network

```
list_network_requests
  urlContains: "theschoolofai.in/api"
  sinceMs: 15000
  detail: summary
```

Record every `/api/*` URL — that is the ground truth for SPA behavior.

### Step E — Inspect a request

```
get_network_request { id: "<from list>" }
```

Observe:

- Cookie names (session-token present; CSRF optional)
- Status codes
- Truncation of cookie values in MCP output (use sqlite/DevTools for full token)

### Step F — Confirm from page JS

```
evaluate_script:
  async () => {
    const r = await fetch('/api/auth/session', { credentials: 'include' });
    return { status: r.status, body: await r.text() };
  }
```

`document.cookie` is often **empty** because the session cookie is HttpOnly.

### Step G — Headless proof

Export token → curl/Python with **only** `Cookie: __Secure-next-auth.session-token=…` and `Accept: application/json`. Confirm 200 and non-empty arrays for sessions/assignments; 401 without cookie.

---

## 5. Key experimental results

| Experiment | Result |
|------------|--------|
| MCP network without remote-debugging-port | Fail — no BiDi network events |
| MCP network with marionette + 9222 | Success — hundreds of requests visible |
| Sessions API with full browser Cookie header | 200 |
| Sessions API with **only** session-token | 200 |
| Sessions API with no cookie | 401 Unauthorized |
| Sessions API with garbage token | 401 |
| `/api/auth/session` no cookie | 200 + `{}` |
| `/api/auth/session` valid cookie | 200 + user object |
| CSRF cookie required for GET data? | **No** |
| Session list includes lesson markdown + video HTML | **Yes** (often complete) |

---

## 6. Sample SPA API set on course page (captured)

```
GET /api/auth/session
GET /api/courses
GET /api/courses/{courseId}
GET /api/courses/{courseId}/sessions
GET /api/assignments?courseId={courseId}
GET /api/quizzes?courseId={courseId}
GET /api/courses/{courseId}/flashcards
GET /api/assignments/{assignmentId}/submission
GET /api/assignments/{assignmentId}/grade
GET /api/notifications?limit=30
GET /api/me/chat/courses
POST /api/activity/heartbeat   (elsewhere)
POST /api/auth/_log
```

Dashboard also used e.g. `/api/dashboard/student`, `/api/daily-check`, `/api/invites/pending`.

---

## 7. Extracting the cookie without DevTools UI

```bash
PROFILE="$HOME/.zen/f7zfdnyw.Default (release)"
# copy if locked
cp "$PROFILE/cookies.sqlite" /tmp/cookies.sqlite

python3 - <<'PY'
import sqlite3
con = sqlite3.connect('/tmp/cookies.sqlite')
for name, value, host in con.execute(
  "SELECT name,value,host FROM moz_cookies WHERE host LIKE '%theschoolofai%'"
):
    print(host, name, len(value))
PY
```

---

## 8. What was deliberately not automated

- Google OAuth click-through (user already logged in; optional manual re-login).
- Storing Google credentials.
- Committing live session tokens or full personal course JSON to git.
- Depending on MCP at collect time.

---

## 9. How to extend discovery for new entities

Example: **grades**

1. `zen-marionette` + Grok MCP session.
2. `navigate_page` → `https://axiom.theschoolofai.in/grades` (or click via snapshot).
3. `list_network_requests` with `urlContains: "/api/"` and recent `sinceMs`.
4. Document new paths in [API_SURFACE.md](./API_SURFACE.md).
5. Add client methods + schema tests + collector flags.
6. Prove with cookie-only curl.

Same pattern for any SPA route: **UI action → network list → minimal curl → code**.

---

## 10. Related paths (history)

Initial collector prototype also lived under the tokenizer assignment tree:

```text
~/timepass/tokenizer-assignment/demo/lab/axiom_collector/
```

**Canonical project (renamed from `tsai-mcp-server` → `tsai-skills`):**

```text
~/timepass/tsai-skills/
  skills/axiom-learning-os/   # Grok skill (preferred agent surface)
  skills/axiom-learning-os/scripts/tsai_skills/            # fetch / collect package
```

---

## 11. Troubleshooting discovery

| Issue | Fix |
|-------|-----|
| MCP “Maximum number of active sessions” | Kill stray `geckodriver` processes; restart Zen |
| Network tools empty/error | Ensure port 9222 BiDi is up; restart Zen with both flags; restart Grok MCP |
| Tabs show “Untitled” | Re-`list_pages`; Zen sometimes lists duplicates |
| Cookie truncated in MCP | Use cookies.sqlite or DevTools Storage |
| Profile lock | Only one Zen instance per profile |
