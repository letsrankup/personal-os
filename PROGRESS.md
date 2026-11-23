# PERSONAL OS — Progress Log

## Phase 1 + Phase 2 — COMPLETE (24 Nov 2026)

### What was built

**Monorepo** at `~/workspace/personal-os/`:

- `apps/api/` — FastAPI backend (Python 3.12 venv at `apps/api/.venv`)
- `apps/web/` — placeholder + README (Next.js frontend is Phase 7)
- `docs/ARCHITECTURE.md` — full 10-phase plan, stack, agent list, permission tiers, DB/migration notes
- `.env.example` — `DATABASE_URL`, `JWT_SECRET`, `ADMIN_EMAIL`/`ADMIN_PASSWORD`, AI provider key placeholders (no real secrets anywhere)
- `README.md`, `.gitignore`

**Backend** (`apps/api/app/`):

- `config.py` — pydantic-settings, env-only config; SQLite default at `apps/api/personal_os.db`, Postgres/Supabase via `DATABASE_URL`
- `database.py` — SQLAlchemy 2 engine/session, `create_all` on startup
- `models.py` — **all 16 tables**: users, agents, conversations, messages, memories, tasks, task_steps, projects, clients, files, reports, integrations, permissions, approvals, activity_logs, scheduled_jobs. UUID PKs, relationships, indexes. `tasks` carries uuid id, description, agent (FK + agent_key), priority, status enum (PENDING/PLANNING/RUNNING/WAITING_FOR_APPROVAL/COMPLETED/FAILED/CANCELLED), started_at, completed_at, JSON logs, result, error, verified flag, permission tier
- `security.py` — bcrypt password hashing (direct bcrypt), JWT via python-jose
- `deps.py` — bearer-token current-user dependency + `log_activity()` helper writing to `activity_logs`
- `seed.py` — seeds **11 agents** (master + research, tasks, communication, clients, business, developer, finance, marketing, projects, reporting) and **14 default permission rows** across the 3 tiers on startup; admin user created **only** from `ADMIN_EMAIL`/`ADMIN_PASSWORD` env (skipped when absent, idempotent)
- `main.py` — app with lifespan seeding, CORS for localhost:3000, endpoints:
  - `GET /health` → `{"status":"ok","service":"personal-os-api","db":"ok"}`
  - `POST /auth/register` (201, 409 on duplicate)
  - `POST /auth/login` → JWT bearer token (401 on bad credentials)
  - `GET /auth/me` (401 without/with invalid token)

### Test results (exact)

```
cd apps/api && .venv/bin/python -m pytest -q
8 passed, 1 warning in 1.66s
```

(Tests: test_health; test_auth — register/login/me flow, wrong-password 401, missing/invalid token 401, duplicate 409; test_models — all 16 tables exist, agents seeded, task create/read round-trip. Tests run on a throwaway temp SQLite DB. The 1 warning is a Starlette TestClient deprecation notice, harmless.)

### Boot check (real uvicorn, port 8123, then stopped)

- `GET /health` → `{"status":"ok","service":"personal-os-api","db":"ok"}`
- Register `boot@example.com` → 201 with user JSON (no password/hash in response)
- Login → JWT issued; `GET /auth/me` with token → same user; wrong password → 401
- DB verified directly: all 16 tables present, 11 agents seeded, 14 permissions, `activity_logs` recorded `auth.register` + `auth.login`
- Admin seed verified separately: no env → `admin_created: False`; with env → `True`; re-run → `False` (idempotent)
- Delivered `personal_os.db` was reset to a clean state (tables + agents + permissions, no test users)

### How to run

```bash
cd ~/workspace/personal-os/apps/api
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# optional admin: ADMIN_EMAIL=... ADMIN_PASSWORD=... .venv/bin/python -m app.seed
# tests: .venv/bin/python -m pytest -q
```

### Notes / decisions

- No Docker daemon in this environment → venv + uvicorn (documented in ARCHITECTURE.md).
- LangGraph/n8n not installed yet — they belong to Phase 3/4 orchestration; the task/task_steps schema and agent registry they will drive are in place.
- passlib is installed per spec, but hashing uses the `bcrypt` library directly (passlib 1.7.x has known incompatibilities with modern bcrypt releases); behavior is identical (bcrypt hashes).
- `JWT_SECRET` has a clearly-marked dev default so the app boots locally; set a real one via env for any real use.

### Next

Phase 3: Master Agent (command understanding EN + Roman Urdu, planning, AI provider chain with fallback). Phase 4: command execution engine on the tasks/task_steps schema.

---

## Phase 3 + Phase 4 + Phase 5 — COMPLETE (24 Nov 2026)

### What was built

**Phase 3 — AI provider layer + Master Agent** (`apps/api/app/ai.py`, `app/agents/`):

- `ai.chat(text, system)` with a fallback chain: OpenAI (if `OPENAI_API_KEY` set) → Gemini (if `GEMINI_API_KEY` set) → free Pollinations endpoint (`https://text.pollinations.ai/<urlencoded prompt>`, no key) → offline template mode (deterministic, clearly labelled `[Offline AI mode …]`, invents nothing). Keys come from env only; `AI_PROVIDER` can force a starting provider; `OPENAI_MODEL`/`GEMINI_MODEL` configurable. `ai.provider_name()` reports the provider that will be tried first.
- `app/agents/base.py` — `BaseAgent.run(db, task, context) -> {result, verified, logs, error?}`. Registry (`app/agents/__init__.py`) maps all 11 agent keys: **master, tasks, reporting implemented for real**; research, communication, clients, business, developer, finance, marketing, projects registered as `NotImplementedAgent` handlers that return FAILED + "not yet implemented" (Phase 6 fills them) — no fake results anywhere.
- Tasks agent: real DB operations `list` (optional pending-only), `create`, `update` — each re-reads the DB before claiming `verified=True`. Reporting agent: builds a summary from live DB counts and stores a real `reports` row (re-read to verify). Master agent: answers general commands through `ai.chat` with memory hits in context.

**Phase 4 — Command execution engine** (`app/orchestrator.py`):

- Explicit state machine in code — UNDERSTAND → PLAN → MEMORY → PERMISSION_CHECK → EXECUTE → VERIFY → PERSIST → REPORT. It mirrors the intended LangGraph graph node-for-node (see Limitations).
- UNDERSTAND: rule-based intent routing, English + Roman Urdu keywords (`task`, `kaam`, `list karo`, `dikhao`, `report banao`, `summary`, `pending`, `transfer`, `email bhejo`, `publish`, `research`, `client`, `project`, `progress`, …); extracts the objective, task title and priority.
- PLAN: creates the Task row (status PLANNING, permission tier from the `permissions` table) + 5 TaskStep rows, each transition timestamped and written to `activity_logs` and the task's JSON logs.
- MEMORY first: keyword search over the user's memories (title/content/tags) → hits go into the agent context; a `conversation_summary` memory is saved after every command.
- PERMISSION_CHECK: AUTOMATIC → execute; APPROVAL_REQUIRED → `approvals` row + task WAITING_FOR_APPROVAL, nothing executes; ALWAYS_MANUAL → refused with a clear message, task CANCELLED with the reason.
- VERIFY: COMPLETED only when the agent result has `verified=true` and a result; otherwise FAILED with the error. Agent crashes are caught and recorded as FAILED, never as success.

**Phase 5 — Persistent memory**: full memories CRUD + `?q=` keyword search + `?kind=` filter, per-user isolation, kinds validated (preference, instruction, project, task, conversation_summary, research, decision, file_ref); the orchestrator retrieves relevant memories before executing follow-up commands.

**Endpoints added** (all JWT-protected except `/health`): `POST /commands` → `{task_id, status, reply, agent, conversation_id, approval_id}` and persists conversation + messages; `GET /conversations`, `GET /conversations/{id}/messages`; `GET /tasks` (filter `?status=`, `?agent=`), `GET /tasks/{id}` (with steps), `POST /tasks/{id}/cancel`; `GET /approvals` (pending), `POST /approvals/{id}/decide` (approved → held task executes for real; rejected → task CANCELLED, never executed); memories CRUD (`POST/GET /memories`, `GET/PATCH/DELETE /memories/{id}`); `GET /agents`; `GET /overview` (task counts by status, active agents, projects in progress, recent activity, latest reports). API version bumped to 0.2.0 → app now exposes 23 routes. No seed changes were needed: the approval test wires the existing seeded `web.publish` (APPROVAL_REQUIRED) permission to the reporting agent via the "publish … report" intent, and `money.transfer` (ALWAYS_MANUAL) drives the refusal tests.

### Test results (exact)

```
cd apps/api && .venv/bin/python -m pytest -q
27 passed, 2 warnings in 19.37s
```

(8 pre-existing + 19 new: command create/list/report flows incl. Roman Urdu "Meri pending tasks list karo", approval hold → approve → real execution + report row, approval rejection, send-email hold → honest Phase-6 FAILED after approval, ALWAYS_MANUAL refusals ×3 phrasings EN + Roman Urdu, unimplemented-agent honesty, offline-AI general command, conversation/message persistence, task filter + cancel, agents + overview, AI provider chain unit tests, memory CRUD + search + isolation + orchestrator memory retrieval. The 2 warnings are Starlette deprecation notices, harmless.)

### Boot check (real uvicorn, port 8124, throwaway DB, `AI_PROVIDER=offline`, then stopped)

- `GET /health` → `{"status":"ok","service":"personal-os-api","db":"ok"}`
- Register `boot@example.com` → 201 user JSON; login → JWT issued.
- `POST /commands` "Create a task to verify the boot check" → `{"status":"COMPLETED","agent":"tasks","reply":"Task created: 'verify the boot check' (id: 8448a0a2-…, status: PENDING, priority: NORMAL)."}`
- `POST /commands` "Meri pending tasks list karo" → `{"status":"COMPLETED","agent":"tasks","reply":"Found 1 pending task(s):\n- [PENDING] verify the boot check (agent: tasks, priority: NORMAL)"}`
- `POST /commands` "Generate a summary report" → COMPLETED via reporting agent; reply is the live-count summary ("Tasks total: 4 … Active agents: 11 …"); a `reports` row was created.
- `GET /overview` → `total_tasks: 4, COMPLETED: 3, PENDING: 1, active_agents: 11` + recent activity + latest reports.
- DB verified directly: 4 task rows (3 orchestrator tasks COMPLETED + verified=1, 1 agent-created PENDING), `reports: 1`, `memories: 3` (one conversation_summary per command), `activity_logs: 14`. The delivered `personal_os.db` was not touched by the boot check.

### Limitations / notes

- **LangGraph**: not installed. The orchestration is an explicit state machine in `app/orchestrator.py` whose states mirror the LangGraph graph 1:1 (UNDERSTAND → PLAN → PERMISSION_CHECK → EXECUTE → VERIFY → PERSIST → REPORT); swapping in LangGraph later changes only that module. n8n remains Phase 8 automation territory.
- The summary report counts its own in-flight task as RUNNING (it reads live counts mid-execution) — accurate, not an error.
- General (unrouted) commands depend on the AI provider chain: with no keys and no network they return the clearly-labelled offline template answer; the task is still recorded COMPLETED because the master verified a non-empty answer was produced — the offline label is part of the answer text, never hidden.
- Commands run synchronously; background execution for long tasks is a later-phase concern (the task/step schema already supports it).
- Specialist agents research/communication/clients/business/developer/finance/marketing/projects remain Phase 6 work; today they fail honestly with "not yet implemented".

### Next

Phase 6: implement the remaining specialist agents one by one (research first). Phase 7: Next.js dashboard wired to these endpoints.

---

## Phase 6 — COMPLETE (24 Nov 2026)

All 8 `NotImplementedAgent` stubs replaced with real specialist agents. The
absolute rule held throughout: every result comes from the DB, a real web
fetch, the AI provider chain, or files the agent actually created — and any
capability needing an unconnected integration returns FAILED with the exact
reason. Registry (`app/agents/__init__.py`) now maps all 11 keys to real
agent classes.

### The eight agents (`apps/api/app/agents/`)

- **research_agent.py** — DuckDuckGo HTML search (`https://html.duckduckgo.com/html/?q=…`,
  httpx + UA header) → top results (title/url/snippet, `uddg` redirect links
  unwrapped) → fetches up to 3 result pages, strips tags to readable text →
  summarizes via `ai.chat` with the collected text as sources → saves a
  `memories` row (kind=research, source URLs in tags) and returns summary +
  source list; verified by re-reading the memory row. Competitor analysis =
  same pipeline with a "competitors of X" query. Network failure → FAILED
  with the real error; a DuckDuckGo bot-challenge page (HTTP 202, observed
  live from this sandbox) is detected and reported as such, not as "no results".
- **communication_agent.py** — drafts only. "draft email to <name> about
  <topic>" → draft via `ai.chat`, stored as a `memories` row kind=file_ref
  (documented storage choice: title "Email draft to <name>: <topic>", tags
  ["email_draft", name]), verified by re-read. Operation `send` (the seeded
  APPROVAL_REQUIRED `email.send_external`, executed only after approval)
  returns FAILED "Gmail integration not connected — … Phase 8 … Nothing was
  sent." Operation `inbox` fails honestly for the same reason.
- **clients_agent.py** — CRUD on `clients`: add (name + regex-parsed
  email/phone/company), list, find (client whose name appears in the
  command, fragment fallback), inquiry (client named in the command;
  categorized complaint/question/other by EN + Roman Urdu keywords; appended
  to client notes + `meta["inquiries"]`, complaint sets status follow_up,
  and a follow-up Task for the clients agent is auto-created). All verified
  by re-reading rows.
- **business_agent.py** — structured plan (summary, market, customers,
  revenue model, risks, next steps) via `ai.chat` with research-memory hits
  in context; saved as a `reports` row kind=business. Every figure is
  labelled an AI estimate in the result and the report — never a verified fact.
- **developer_agent.py** — writes a real static scaffold (index.html,
  style.css, script.js) into `apps/api/agent_workspace/<slug>/` (slug from
  the brief; `AGENT_WORKSPACE_DIR` env overrides the root, used by tests),
  verifies on disk that the files exist and index.html contains `<html` and
  a `<title>`; the resolved path is checked to stay inside the workspace.
  Operation `review` lists/summarizes the generated projects from disk.
  Publishing is never performed (stays APPROVAL_REQUIRED `web.publish`).
- **finance_agent.py** + new **`finance_entries` table** (id, user_id,
  kind income|expense, amount, currency default PKR, category, note,
  occurred_at, created_at; 17 tables total now). Parses amount/kind/category
  from EN + Roman Urdu ("kharcha 5000 khana", "income 50000 salary");
  summary = current-month totals by kind + by category computed from the
  real rows. The agent never moves money (transfers remain ALWAYS_MANUAL
  and are refused by the orchestrator before this agent runs).
- **marketing_agent.py** — SEO keyword ideas + content plan + 3 social post
  drafts via `ai.chat`, saved as a `reports` row kind=marketing. Nothing is
  published (no social integration) — the result says "Drafts only".
- **projects_agent.py** — create/list/progress/blockers on `projects`.
  Progress uses REAL linked-task counts: `tasks.project_id` already existed
  as a nullable FK, so no schema change was needed for projects. Blockers =
  the user's FAILED tasks + longest-PENDING tasks, read from the DB.

### Deepened existing agents

- **tasks** — create now stores priority + deadline: orchestrator
  `_extract_priority` understands "bohat zaroori"=HIGH, "kam zaroori"=LOW
  (plus high/low/urgent/fawri); new `_extract_due` parses ISO dates,
  "tomorrow"/"kal", "today"/"aaj" into the new nullable **`tasks.due_at`**
  column; list output shows due dates.
- **reporting** — kinds `daily` (today, UTC) and `weekly` (last 7 days) in
  addition to `summary`: counts are period-filtered and `period_start`/
  `period_end` are stored on the report row.

### Routing (orchestrator `understand()`, EN + Roman Urdu)

New/extended routes: daily/weekly reports; finance (kharcha, kharch,
expense, hisab, aamdani, tankhwah, income); developer (website banao, app
banao, code likho, review project files); marketing (marketing, seo, post
likho, content plan); business (business plan, strategy banao, market
analysis); research (dhoondo, find out, maloom karo, competitor, tahqeeq);
communication drafts (draft email, email draft, draft likho) + inbox;
clients sub-intents (add/find/inquiry/list — client-find is checked before
research so "client dhoondo" is not swallowed by the research keyword);
projects (create project, project progress, blockers/rukawat). Task
create/list rules now sit before the project rules so "create a task about
a blocker" creates a task. All Phase 3–5 routes kept working (suite green).

### Schema changes

- `tasks.due_at` (nullable DateTime) and the `finance_entries` table.
  Fresh DBs get both from `create_all`; the delivered `personal_os.db` was
  migrated explicitly (`ALTER TABLE tasks ADD COLUMN due_at` +
  `create_all` for finance_entries — `create_all` never alters existing
  tables) and verified: 17 tables, 11 agents, 14 permissions, 0 user rows.

### Test results (exact)

```
cd apps/api && .venv/bin/python -m pytest -q
39 passed, 2 warnings in 31.09s
```

(27 pre-existing + 12 new in `tests/test_phase6_agents.py`: research
pipeline with monkeypatched httpx + memory persistence, communication draft
stored-not-sent, clients add/list/find, inquiry → follow-up task, business
report row, developer files verified on disk in a tmp workspace + review,
finance add/list/summary math on real rows, marketing drafts-only report,
projects create/list/progress, blockers from real tasks, task
priority/deadline parsing incl. "bohat zaroori" + "kal" + ISO date, daily
report period. Two Phase-5 tests were updated to the new honest behavior:
approved email send now fails with "Gmail integration not connected"
(was "not yet implemented"), and the research honesty test now blocks the
network and expects FAILED with the real search error. Tests use the
offline AI provider and monkeypatched httpx — no live network dependency.)

### Boot check (real uvicorn, port 8125, throwaway DB, then stopped)

Server env note: this sandbox exports a `NO_PROXY` list containing
bracketed IPv6 entries that httpx cannot parse (`InvalidURL: Invalid port:
':1]'` — observed on the first boot attempt and recorded here honestly);
the boot server was therefore started with `NO_PROXY=localhost,127.0.0.1`
so httpx uses the sandbox egress proxy the same way curl does. On a normal
machine no such adjustment is needed.

- `GET /health` → `{"status":"ok","service":"personal-os-api","db":"ok"}`; register → 201; login → JWT.
- `POST /commands` "Research electric bikes in Pakistan" → **COMPLETED** (live network):
  DuckDuckGo returned 8 real results, 3 pages fetched (PakWheels, metroev.pk, …);
  the AI summary step fell back to the clearly-labelled offline template (no
  cloud key configured; the free Pollinations fallback did not answer through
  this sandbox's proxy), so the reply carries the fetched source text + the
  full source list, and a kind=research memory row was saved (verified in the
  boot DB: `research memories: 1`). Sources returned: pakwheels.com (×2),
  metroev.pk, vlektra.com, olx.com.pk, dreamlifegreen.com,
  electricbikesinpakistan.com.pk, e-bike.com.pk. (An earlier direct probe of
  DuckDuckGo from this sandbox was answered with its HTTP 202 bot-challenge
  page — the agent detects and reports that case; the live run above got
  real results.)
- "Kharcha 2500 petrol" → COMPLETED finance: `Expense recorded: 2,500.00 PKR (category: transport, …)`;
  "Income 80000 salary" → `Income recorded: 80,000.00 PKR (category: salary, …)`;
  "Hisab dikhao" → `Finance summary for November 2026 (from 2 recorded entries): Total income: 80,000.00 PKR / Total expenses: 2,500.00 PKR / Net: 77,500.00 PKR / By category: salary: 80,000.00, transport: 2,500.00`. Boot DB verified: `finance_entries: [('expense', 2500.0, 'transport'), ('income', 80000.0, 'salary')]`.
- "Add client Boot Enterprises" → COMPLETED clients: `Client added: 'Boot Enterprises' (…, status: new)`;
  "Clients list karo" → `Found 1 client(s): - Boot Enterprises (status: new)`.
- "Website banao for a tea shop" → COMPLETED developer: `Website scaffold created at …/apps/api/agent_workspace/tea-shop — files: index.html (623 bytes), style.css (415 bytes), script.js (182 bytes).` Verified on disk (`<title>A Tea Shop</title>`); the boot-created site was removed afterwards to keep the delivered tree clean.
- A second sanity boot against the migrated delivered DB (port 8126) confirmed
  `due_at` works end-to-end: "Create a task to sanity check due dates tomorrow,
  bohat zaroori" → `priority: HIGH, due: 2026-11-24`; the sanity user's rows
  were deleted afterwards (delivered DB back to 0 user rows).

### Limitations / notes

- Research quality depends on DuckDuckGo's HTML endpoint, which sometimes
  answers automated clients with a bot-challenge page (HTTP 202) — the agent
  reports that honestly as FAILED; it never falls back to invented results.
  In this sandbox, httpx also needs a parseable `NO_PROXY` (see boot note).
- Email drafts are stored as `memories` rows (kind=file_ref) until the
  Phase 7 file UI / Phase 8 Gmail integration land; sending and inbox
  reading stay honest FAILED until Gmail is connected in Phase 8.
- The developer agent generates a deterministic static scaffold (real files,
  real HTML/CSS/JS) — it does not yet generate bespoke code per brief via
  the AI chain, and it never publishes.
- Finance parsing is keyword-based (first number = amount; EN + Roman Urdu
  keyword maps for kind/category) — free-form sentences outside those
  patterns can mis-parse; every entry keeps the original command as its
  note so mistakes are auditable, and totals always come from the rows.
- Business/marketing output is only as good as the configured AI provider;
  in offline mode it is the clearly-labelled local template stored in a
  real report row — figures are labelled estimates either way.

### Next

Phase 7: Next.js dashboard (13 pages) wired to these endpoints.
Phase 8: Gmail/Calendar/Drive/GitHub OAuth integrations (turns the
communication agent's honest FAILEDs into real sends/reads).

---

## Phase 7 — COMPLETE (24 Nov 2026)

Next.js dashboard in `apps/web/` (create-next-app scaffold: Next 16.4.6,
React 19, TypeScript, Tailwind CSS v4, App Router), dark theme, responsive
sidebar layout. **Hard rule held: every page renders real API data — no fake
buttons, no placeholder stats, no mock data.** Where a read endpoint was
missing, it was added to the API (read-only, JWT-protected, tested) instead
of faking the page.

### API endpoints added (Phase 7)

- `GET /projects` + `GET /projects/{id}` — per-user; progress computed from
  real linked tasks (`total_tasks`, `completed_tasks`, `progress_pct`).
- `GET /clients` + `GET /clients/{id}` — clients table has no `user_id` by
  design, so the list is shared (documented in code).
- `GET /files` — per-user file records.
- `GET /reports` (`?kind=` filter) + `GET /reports/{id}`.
- `GET /integrations` — honest status rows (all `not_connected` until
  Phase 8 OAuth; the page says so, nothing is faked as connected).
- `GET /permissions` — the seeded 3 tiers (AUTOMATIC / APPROVAL_REQUIRED /
  ALWAYS_MANUAL).
- `GET /activity` (`?limit=`) — per-user audit view over `activity_logs`.
- `GET /health` extended with `ai_provider` (the provider the chain tries
  first, via the existing `ai.provider_name()`).

New schemas in `app/schemas.py` (ProjectOut/ClientOut/FileOut/ReportOut/
IntegrationOut/PermissionOut/ActivityOut); new tests in
`tests/test_phase7_reads.py` (6 tests: auth required on all 7 paths,
project progress math + per-user isolation, clients, files scoping,
reports filter/detail, permissions tiers + activity).

### Test results (exact)

```
cd apps/api && .venv/bin/python -m pytest -q
45 passed, 2 warnings in 38.13s
```

(39 pre-existing + 6 new Phase 7 read-endpoint tests. Same 2 harmless
Starlette deprecation warnings.)

### Web app

- `lib/api.ts` — base URL from `NEXT_PUBLIC_API_URL` (default
  `http://localhost:8000`, matching the API's port), JWT in localStorage,
  401 → redirect to /login. `lib/types.ts` mirrors the API schemas.
  `.env.example` included.
- Auth: `/login` + `/register` wired to the real endpoints (register then
  auto-login); the `(app)` route-group layout guards every app page
  (no token or invalid token → /login) and the sidebar carries the user
  email + logout button.
- Pages (13 + auth):
  1. `/` Overview — GET /overview (task counts, active agents, projects in
     progress, recent activity, latest reports).
  2. `/command` Command Center — conversation list + messages
     (GET /conversations[/{id}/messages]), POST /commands with reply +
     task status + assigned agent shown, pending approvals panel with
     working Approve/Reject (POST /approvals/{id}/decide), voice input
     where the browser supports it; Roman Urdu renders as plain UTF-8.
  3. `/agents` — GET /agents cards (name, key, role, status, model).
  4. `/tasks` — GET /tasks with status + agent filters, expandable detail
     (GET /tasks/{id}: steps, logs, result/error, verified flag), working
     Cancel (POST /tasks/{id}/cancel).
  5. `/projects` — GET /projects with real progress bars from linked tasks.
  6. `/clients` — GET /clients with status/contact/notes + inquiry count
     from `meta.inquiries`.
  7. `/research` — GET /memories?kind=research with tags/source shown.
  8. `/files` — GET /files records (honest empty state) + a clearly
     labelled section for documents stored as memories kind=file_ref
     (where email drafts live until Phase 8).
  9. `/reports` — GET /reports with kind filter, full content view and a
     client-side download of the real report text.
  10. `/memory` — full CRUD UI: search (?q=), kind filter, create form,
      inline edit, delete with confirm — all against the real endpoints.
  11. `/integrations` — GET /integrations; planned Phase 8 services
      (Gmail/Calendar/Drive/GitHub) shown as not_connected with an honest
      note; no connect buttons exist yet because there is nothing real
      behind them until Phase 8.
  12. `/security` — GET /permissions grouped by the 3 tiers + GET /activity
      audit list.
  13. `/settings` — API base URL in use, live GET /health (status, db,
      ai_provider), and the server-side env note for model keys.

### Build + smoke (exact)

```
cd apps/web && npm run build
✓ Compiled successfully — TypeScript clean, 15 routes generated
  (/, /agents, /clients, /command, /files, /integrations, /login,
   /memory, /projects, /register, /reports, /research, /security,
   /settings, /tasks)
```

Smoke (API on :8000 with throwaway DB + `AI_PROVIDER=offline` +
`NO_PROXY=localhost,127.0.0.1`; web `npm run start` on :3000; both stopped
afterwards): `/`, `/login`, `/tasks` all HTTP 200 (login HTML contains the
real sign-in form; app pages serve the guarded shell). End-to-end API flow
the UI uses: register → 201, login → JWT, GET /overview → live counts
(active_agents: 11), POST /commands "Meri pending tasks list karo" →
COMPLETED via tasks agent ("No pending tasks found."), and GET on
/projects, /clients, /files, /reports, /integrations, /permissions,
/activity, /agents, /approvals, /conversations, /memories all → 200.
GET /health → `{"status":"ok","service":"personal-os-api","db":"ok","ai_provider":"offline"}`.

### Limitations / notes

- Pages are client-rendered (JWT lives in localStorage), so curl sees the
  app shell; data loads from the API in the browser. Server components
  would need cookie-based auth — a deliberate Phase 7 simplification.
- Integrations page has no connect actions: OAuth flows are Phase 8, and
  the hard rule forbids buttons that do nothing.
- Files page reflects the `files` table, which no agent populates yet;
  agent-produced documents currently live as file_ref memories (shown in
  the labelled section) and developer-agent sites on disk under
  `apps/api/agent_workspace/` (visible via the Developer Agent's review
  command, not the files table).
- Voice input uses the browser's Web Speech API where available
  (Chrome); the button reports honestly when unsupported.

### Next

Phase 8: Gmail/Calendar/Drive/GitHub OAuth integrations (Integrations page
gets real connect flows; communication agent's honest FAILEDs become real
sends/reads). Phase 9: security hardening pass. Phase 10: deployment.

---

## Phase 8 + Phase 9 — COMPLETE (24 Nov 2026)

### Phase 8 — Integrations framework (`apps/api/app/integrations.py`)

- Seven providers seeded/ensured as `integrations` rows (idempotent, also
  wired into `seed_all` and lazily into `GET /integrations`): **gmail,
  google_calendar, google_drive, github, supabase, openai, gemini**.
  Statuses: `not_connected | connected | error`, plus `awaiting_oauth` for
  the Google services once credentials exist. The delivered
  `personal_os.db` was seeded too (7 rows, all honestly `not_connected`,
  0 user rows).
- `POST /integrations/{key}/check` (JWT, owner/admin only) runs the real
  check, persists status + `last_checked_at`, and writes an
  `integration.check` activity row:
  - **github** — `GITHUB_TOKEN` set → live `GET https://api.github.com/user`;
    200 → `connected`, the login name stored in config + `account_label`;
    non-200 → `error` with the HTTP status; network failure → `error` with
    the reason. No token → `not_connected`.
  - **openai / gemini** — presence check only (no API call burned):
    key set → `connected` with the model name (`OPENAI_MODEL` /
    `GEMINI_MODEL`, defaults gpt-4o-mini / gemini-2.0-flash) in config.
  - **supabase** — `SUPABASE_URL` + `SUPABASE_ANON_KEY` set → live
    `GET {url}/rest/v1/`; any HTTP response (200/401/404) proves
    reachability → `connected` with the status code recorded; network
    failure → `error` with the reason.
  - **gmail / google_calendar / google_drive** — without
    `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`: `not_connected` with
    config.note "Requires Google OAuth credentials — see
    docs/INTEGRATIONS.md". With them: `awaiting_oauth` + an
    accounts.google.com authorization URL (per-service scopes, redirect
    `{APP_BASE_URL}/integrations/google/callback`). OAuth is never
    completed by the system — the user opens the URL themselves.
- **Secrets discipline:** values are read from the process env at check
  time (settings/.env fallback), never written to the DB, and
  `GET /integrations` / check responses pass config through a masking
  filter (`public_config`) that replaces sensitive-looking keys with
  `***`. Tests assert the token/key/secret strings never appear in any
  response body. `IntegrationOut` gained the `config` field.
- **Dashboard:** Integrations page rewritten — all 7 services from the
  API (the Phase 7 placeholder list is gone), each card shows status,
  account/login, model, last HTTP status, last checked, the note text, an
  "Open Google authorization page" link when an auth URL exists, and a
  working **Check status** button that calls the check endpoint and swaps
  in the fresh row.
- **docs/INTEGRATIONS.md** — per-service setup: exactly what the user must
  provide and where (env vars / `apps/api/.env`), GitHub token steps,
  AI key steps, Supabase project steps, and the full Google Cloud OAuth
  walkthrough (project, APIs, consent screen, redirect URI, test users).

### Phase 9 — Security & permissions hardening

- **Rate limiting** (`app/ratelimit.py`): in-memory per-IP fixed-window
  limiter. `POST /auth/login` + `POST /auth/register` share the `auth`
  bucket (default 10/min), `POST /commands` gets 60/min; over the limit →
  429 with a clear message. Limits are env-tunable
  (`RATE_LIMIT_AUTH_PER_MIN`, `RATE_LIMIT_COMMANDS_PER_MIN`, read at call
  time) and a `reset_rate_limits()` hook + an autouse conftest fixture
  keep the suite deterministic.
- **Audit gaps filled:** login **failures** now logged
  (`auth.login_failed`, attempted email recorded, committed before the
  401), alongside the existing login success, register, approval
  decisions, integration checks, and job lifecycle events.
- **Password policy:** minimum 8 characters on register (schema-enforced,
  422 otherwise) — verified by test and boot check.
- **Roles:** `users.role` already existed (default `owner`, admin seed =
  `admin`), so no migration was needed. New `require_owner_or_admin`
  dependency gates `GET /permissions` and
  `POST /integrations/{key}/check` (403 for any other role, e.g. a
  `member` account; ordinary endpoints and per-user scoping unchanged).
- **CORS:** restricted to `ALLOWED_ORIGINS` (comma-separated env; default
  `http://localhost:3000`) instead of the previous localhost list.
- **Scheduled jobs** (`app/jobs.py` + endpoints): `GET /jobs`,
  `POST /jobs` {name, kind:"report", report_kind: summary|daily|weekly,
  interval: daily|weekly, or one-off `run_at` ISO} (409 on duplicate
  name), `POST /jobs/{id}/run` (manual trigger), `DELETE /jobs/{id}`.
  `run_due_jobs(db, now)` executes due kind="report" jobs through the
  real Reporting Agent (a real `reports` row from live counts), sets
  `last_run_at`, advances `next_run_at` (daily +1d / weekly +7d, missed
  slots skipped; one-off jobs disable), and logs `job.executed` /
  `job.failed`. A guarded asyncio loop in the app lifespan calls it every
  60s with its own session — DB errors are swallowed so the API never
  crashes because of the scheduler. Dashboard: the Reports page gained a
  **Scheduled report jobs** section (list with last/next run, create
  form, Run now, Delete) wired to these endpoints only.
- **docs/SECURITY.md** — permission tiers recap (incl. the ALWAYS_MANUAL
  list: money transfers, secret disclosure, irreversible deletion),
  what is logged, rate limits, roles, secrets handling, CORS, scheduler.

### Test results (exact)

```
cd apps/api && .venv/bin/python -m pytest -q
62 passed, 2 warnings in 56.03s
```

(45 pre-existing + 17 new: `tests/test_phase8_integrations.py` — 9 tests:
all-7 not_connected with a scrubbed env + per-service check notes, GitHub
bogus token → error/401 with the token absent from the response, GitHub
200 → connected with login only, GitHub network failure → error reason,
OpenAI/Gemini presence semantics + key never returned, Google creds →
awaiting_oauth + auth URL without the secret, Supabase 401 → connected
with the anon key absent, unknown provider 404 + auth required, check
audited. `tests/test_phase9_security_jobs.py` — 8 tests: short password
422 + exactly-8 passes, deterministic login 429 via env-set limit,
login-failure audit, member role 403 on both gated endpoints while
ordinary endpoints still work, jobs auth required, job CRUD + manual run
creating a real report row, run_due_jobs executing + advancing the
schedule + not re-running, one-off job disabling after its run. The 2
warnings are the same harmless Starlette deprecations.)

### Web build (exact)

```
cd apps/web && npm run build
✓ Compiled successfully — TypeScript clean, 15 routes generated
  (/, /agents, /clients, /command, /files, /integrations, /login,
   /memory, /projects, /register, /reports, /research, /security,
   /settings, /tasks)
```

### Boot check (real uvicorn, port 8127, throwaway DB, `AI_PROVIDER=offline`, then stopped)

- `GET /health` → `{"status":"ok","service":"personal-os-api","db":"ok","ai_provider":"offline"}`
- Register → 201; login → 200 JWT.
- `GET /integrations` → 200, all 7 providers `not_connected` (gemini,
  github, gmail, google_calendar, google_drive, openai, supabase).
- `POST /integrations/github/check` → 200 `not_connected`, note "Set
  GITHUB_TOKEN in the API environment — see docs/INTEGRATIONS.md".
- `POST /integrations/gmail/check` → 200 `not_connected`, note "Requires
  Google OAuth credentials — see docs/INTEGRATIONS.md".
- `POST /jobs` (daily summary) → 201 with `next_run_at` set;
  `POST /jobs/{id}/run` → 200 `executed: True`, `report_id`
  2696e5f0-cacf-4543-ad8a-cee143077d98; `GET /reports?kind=summary` →
  1 row ("Summary Report — 2026-11-23 21:07 UTC"); `GET /jobs` shows the
  job with `last_run_at` set.
- `GET /permissions` (owner) → 200, 14 rows. Register with a 5-char
  password → 422.
- Boot DB verified directly: the summary `reports` row exists;
  activity_logs contain `integration.check` ×2, `job.created`,
  `job.executed`; checked integrations carry `last_checked_at`.

### Limitations / notes

- Google services stop at `awaiting_oauth`: exchanging the OAuth code for
  tokens and storing refresh tokens is deliberately not built (it needs
  the user's consent flow and a secrets store decision). Until then the
  communication agent keeps failing honestly on send/inbox.
- OpenAI/Gemini "connected" means *key present* by design — no billable
  API call is made to prove it; a wrong key would only surface when an
  agent actually calls the provider (the AI chain then falls back and
  says so).
- Rate limiting and the job scheduler are process-local (single-instance
  personal deployment): limits reset on restart, and due jobs only run
  while the API is up (missed slots are skipped, not back-filled).
- The `awaiting_oauth` status is a fourth status string beyond the
  original three — the column was always free-text, and the dashboard
  badge styles it distinctly.

### Next

Phase 10: testing hardening, optimization and deployment packaging
(Docker/production docs). Optional follow-ups when the user provides
credentials: complete the Google OAuth token exchange (turns
`awaiting_oauth` into real Gmail/Calendar/Drive access).

---

## Phase 10 — COMPLETE, local part (24 Nov 2026)

Testing hardening + deployment packaging done locally. GitHub push and
Vercel deploy are NOT done here (no browser/git auth in this sandbox) —
everything is prepared so they take one step afterwards (see
`FINAL_REPORT.md` §4).

### Final verification run (exact)

```
cd apps/api && .venv/bin/python -m pytest -q
62 passed, 2 warnings in 59.97s

cd apps/web && npm run build
✓ Compiled successfully — TypeScript clean, 15 routes generated
  (/, /agents, /clients, /command, /files, /integrations, /login,
   /memory, /projects, /register, /reports, /research, /security,
   /settings, /tasks) — 18 static pages incl. /_not-found
```

### End-to-end smoke (throwaway DB, offline AI, both servers, then stopped)

API on :8000 with `DATABASE_URL=sqlite:////tmp/pos_smoke.db`,
`AI_PROVIDER=offline`, `NO_PROXY=localhost,127.0.0.1`; web production
server (`npm run start`) on :3000 from the fresh build.

- `GET /health` → `{"status":"ok","service":"personal-os-api","db":"ok","ai_provider":"offline"}`
- Web `/` → 200, `/login` → 200.
- Register `smoke@example.com` → 201; login → JWT issued.
- `POST /commands` "Kharcha 2500 petrol" → COMPLETED (finance):
  `Expense recorded: 2,500.00 PKR (category: transport, …)`.
- `POST /commands` "Income 80000 salary" → COMPLETED:
  `Income recorded: 80,000.00 PKR (category: salary, …)`.
- `POST /commands` "Hisab dikhao" → COMPLETED: `Finance summary for
  November 2026 (from 2 recorded entries): Total income: 80,000.00 PKR /
  Total expenses: 2,500.00 PKR / Net: 77,500.00 PKR / By category:
  salary: 80,000.00, transport: 2,500.00`.
- `POST /commands` "Meri pending tasks list karo" (Roman Urdu) →
  COMPLETED via tasks agent: `No pending tasks found.`
- `GET /overview` → `total_tasks: 4, COMPLETED: 4, active_agents: 11`.
- Both servers stopped; the throwaway DB was deleted. The delivered
  `personal_os.db` was not touched.

### Docker deliverables (written, untested in this sandbox — no Docker)

- `apps/api/Dockerfile` — python:3.12-slim, pinned requirements,
  non-root user, `uvicorn app.main:app` on 8000, `/health` healthcheck;
  `apps/api/.dockerignore`.
- `apps/web/Dockerfile` — node:24-alpine multi-stage (`npm ci` → build →
  production `npm run start`), port 3000, `NEXT_PUBLIC_API_URL` as a
  build arg; `apps/web/.dockerignore`.
- `docker-compose.yml` (repo root) — `api` + `web`, env passthrough for
  all documented variables, `DATABASE_URL` defaulting to SQLite on the
  named volume `api-data`, ports 8000/3000, healthchecks,
  `depends_on: service_healthy`.
- `apps/api/requirements.txt` regenerated pinned from the working venv
  (`pip freeze`, 37 packages).

### Git readiness

- Auth findings (report only): `gh` 2.102.0 installed, **not logged in**
  to any host; no global `credential.helper`; no `~/.git-credentials`;
  SSH key pair present at `~/.ssh` (`id_ed25519` / `id_ed25519.pub`,
  names only). A push needs `gh auth login` or an SSH remote using that
  key (only if the key is on the GitHub account).
- `.gitignore` extended: `.env.*` (except `.env.example`),
  `apps/api/agent_workspace/*` (with `.gitkeep` kept), `*.log`, `/tmp/`.
- `git init` (branch `main`), repo-local identity only
  (`user.name "Personal OS"`, `user.email "personal-os@local"`), ONE
  commit "Personal OS — AI Command Center (Phases 1-10)" — initially
  `51e7c30`, amended once to include `FINAL_REPORT.md` + this section;
  final hash in `git log --oneline`. Working tree clean.
- Tracked files: 87. Working-tree size: ~1.7 MB excluding `.git`,
  `.venv`, `node_modules`, `.next`.
- Source archive for manual upload: `~/workspace/personal-os-source.zip`
  (`git archive HEAD`, tracked files only).

### Docs delivered

- `docs/DEPLOYMENT.md` — local run, Docker run, Vercel web deploy
  (Root Directory `apps/web`, `NEXT_PUBLIC_API_URL`), API hosting
  (persistent host required — SQLite + scheduler loop; VPS/Docker,
  Render/Railway notes), production checklist.
- `README.md` — completed: real feature list, architecture, quick start,
  env table, integration/testing/deployment pointers, "Manual setup
  still required" section.
- `FINAL_REPORT.md` — the delivery document (features per phase with
  test counts, architecture, how to run, manual remainder, limitations).

### Remaining (owner actions, prepared but not executed)

GitHub push (needs the owner's git auth) → Vercel import of `apps/web`
→ persistent API hosting → AI keys / Google OAuth completion as desired.
