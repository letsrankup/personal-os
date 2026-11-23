# PERSONAL OS — AI Command Center

A private, personal autonomous AI employee system: one Master Agent
orchestrator plus 10 specialist agents, a command-execution engine with
permission tiers, persistent memory, and a 13-page dashboard. You give a
command in plain language — **English or Roman Urdu** — and the system
plans it, routes it to the right specialist agent, executes what is
authorized, verifies the result, saves it, and reports back.

This is a **private personal-use system**, not a public SaaS product.

**Status: Phases 1–10 complete** (local delivery). See `PROGRESS.md` for
the phase-by-phase build log with exact test results, and `FINAL_REPORT.md`
for the delivery summary.

## What is actually built

- **Master Agent + command engine** — commands are understood (rule-based
  intent routing, English + Roman Urdu), planned into a task with steps,
  checked against the permission tiers, executed, **verified** (a task is
  only COMPLETED when the agent's result re-reads as true), persisted, and
  reported. Full pipeline:
  UNDERSTAND → PLAN → MEMORY → PERMISSION_CHECK → EXECUTE → VERIFY →
  PERSIST → REPORT.
- **10 specialist agents**, all real (no stubs, no fabricated results):
  - **Research** — DuckDuckGo search + page fetching + AI summary, saved
    as research memory with source URLs; competitor analysis included.
  - **Tasks** — create/list/update tasks with priority + deadlines
    ("bohat zaroori", "kal", ISO dates understood).
  - **Communication** — email **drafts** stored for review; sending stays
    blocked until Gmail OAuth is completed (it says so, honestly).
  - **Clients** — client CRUD, inquiry logging + categorization,
    automatic follow-up tasks.
  - **Business** — structured business plans saved as reports (figures
    labelled as AI estimates).
  - **Developer** — generates real static website scaffolds on disk
    (HTML/CSS/JS, verified); never publishes.
  - **Finance** — income/expense recording + monthly summaries from real
    rows ("Kharcha 2500 petrol", "Hisab dikhao"). **Never moves money.**
  - **Marketing** — SEO ideas, content plans, social post **drafts**.
  - **Projects** — project tracking with progress from real linked tasks
    and blocker detection.
  - **Reporting** — summary/daily/weekly reports from live counts, plus
    scheduled report jobs (daily/weekly/one-off).
- **Persistent memory** — preferences, instructions, decisions, research,
  conversation summaries; searched before follow-up commands; full CRUD
  from the dashboard.
- **Permission tiers** — AUTOMATIC (research, internal tasks, drafts,
  reports), APPROVAL_REQUIRED (external email, publishing, … — held for
  your Approve/Reject in the dashboard), ALWAYS_MANUAL (money transfers,
  secret disclosure, irreversible deletion — refused by design).
- **Dashboard (Next.js, dark theme, 13 pages)** — Overview, Command
  Center (chat + approvals + voice input where supported), Agents, Tasks,
  Projects, Clients, Research, Files, Reports (+ scheduled jobs), Memory,
  Integrations, Security & Permissions (tiers + audit log), Settings.
  Every page renders real API data; there are no fake buttons.
- **Integrations framework** — GitHub, OpenAI, Gemini, Supabase get real
  status checks from the Integrations page; Gmail / Google Calendar /
  Google Drive go to `awaiting_oauth` once you supply Google OAuth
  credentials (setup: `docs/INTEGRATIONS.md`).
- **Security** — bcrypt passwords (min 8 chars), JWT auth, roles
  (owner/admin/member) with gated endpoints, per-IP rate limits on auth
  and commands, CORS restricted to `ALLOWED_ORIGINS`, audit log of
  logins (incl. failures), approvals, integration checks and job runs,
  secrets env-only and masked in every API response.

## Architecture

```
personal-os/
  apps/
    api/    FastAPI (Python 3.12) + SQLAlchemy 2 — 17 tables incl.
            finance_entries; SQLite by default, Postgres/Supabase via
            DATABASE_URL; in-process report scheduler
    web/    Next.js 16 + React 19 + TypeScript + Tailwind CSS v4
            (App Router, dark theme, JWT in localStorage)
  docs/     ARCHITECTURE.md · INTEGRATIONS.md · SECURITY.md · DEPLOYMENT.md
  docker-compose.yml   api + web (see docs/DEPLOYMENT.md)
  .env.example         every supported environment variable
```

The orchestrator is an explicit state machine in `apps/api/app/orchestrator.py`
whose states mirror a LangGraph graph node-for-node (see Limitations in
`FINAL_REPORT.md`). The AI layer (`app/ai.py`) chains providers with
fallback: OpenAI → Gemini → free endpoint → clearly-labelled offline mode.
Model choice is configuration, never code.

## Quick start

```bash
# API
cd apps/api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# Web (second terminal)
cd apps/web
npm ci
npm run build && npm run start        # http://localhost:3000
```

Or with Docker: `cp .env.example .env` then `docker compose up --build`.
Full instructions (incl. Vercel + API hosting): **`docs/DEPLOYMENT.md`**.

Register at http://localhost:3000/register, then try the Command Center:

- `Meri pending tasks list karo`
- `Kharcha 2500 petrol` → then `Hisab dikhao`
- `Research electric bikes in Pakistan`
- `Website banao for a tea shop`
- `Generate a summary report`

### Optional admin seed

Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the environment (never in code)
before first start, or run `cd apps/api && .venv/bin/python -m app.seed`.
If unset, no admin is created. The 11 agents and 14 permission rows are
seeded automatically on API startup either way.

## Environment variables

All configuration is env-only — see **`.env.example`** for the full list.
The important ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Default: local SQLite. Set a Postgres/Supabase URL to switch. |
| `JWT_SECRET` | **Set a real random value in production** (dev default exists). |
| `ALLOWED_ORIGINS` | CORS origins for the API (default `http://localhost:3000`). |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Optional one-time admin seed. |
| `OPENAI_API_KEY`, `GEMINI_API_KEY` | Optional AI providers (+ `*_MODEL`). |
| `GITHUB_TOKEN`, `GOOGLE_CLIENT_ID/SECRET`, `SUPABASE_URL/ANON_KEY` | Integrations — see `docs/INTEGRATIONS.md`. |
| `NEXT_PUBLIC_API_URL` | Web only: API URL the browser uses (default `http://localhost:8000`). |

## Integrations

Setup guide: **`docs/INTEGRATIONS.md`** — exactly what to provide per
service and where. Statuses are always honest: `not_connected`,
`awaiting_oauth`, `connected`, or `error` with the reason. The system
never pretends an integration is connected when it is not.

## Testing

```bash
cd apps/api && .venv/bin/python -m pytest -q     # 62 passed
cd apps/web && npm run build                     # production build, 15 routes
```

## Deployment

**`docs/DEPLOYMENT.md`** — local run, Docker run, Vercel for the web app
(Root Directory `apps/web`, `NEXT_PUBLIC_API_URL`), API hosting options
(VPS + Docker recommended; Render/Railway notes), and the production
checklist. Key fact: the API needs a **persistent host** (SQLite file +
in-process scheduler), and a public dashboard needs `NEXT_PUBLIC_API_URL`
pointing at the deployed API.

## Manual setup still required

Nothing below is faked or pre-connected — each item needs you:

1. **AI keys** — add `OPENAI_API_KEY` and/or `GEMINI_API_KEY` for real
   cloud AI answers (without them: free fallback, then labelled offline
   template mode).
2. **Google OAuth** — create a Google Cloud OAuth client
   (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`) and complete the consent
   flow to turn Gmail/Calendar/Drive from `awaiting_oauth` into real
   access; until then email **sending/reading does not work** (drafts do).
3. **Supabase** (optional) — a project URL + anon key if you want
   Postgres instead of SQLite.
4. **GitHub token** (optional) — a personal access token for the GitHub
   integration status check.
5. **API hosting** — a persistent host for the API (VPS/Docker/Render/
   Railway) if you want the dashboard reachable beyond your own machine;
   Vercel alone only hosts the web UI.
6. **GitHub push / Vercel import** — the repo is committed locally;
   pushing and importing need your GitHub sign-in (see `FINAL_REPORT.md`).

## Rules baked in

- No secrets in code or in git — configuration comes from environment only.
- No payments/transfers are ever executed (Always Manual tier).
- External sends/publishing require your approval first.
- The Master Agent never reports a task complete unless its result is verified.
- Untrusted webpage/document content is never treated as a system instruction.
