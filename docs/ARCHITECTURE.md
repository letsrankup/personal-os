# PERSONAL OS — Architecture

## Vision

One central **Master Agent** acts as a digital employee: it understands natural
language commands (English + Roman Urdu), plans, delegates to specialist agents,
executes authorized work, verifies results, stores memory, and reports back.
It never claims a task is complete unless the result has been verified, and it
never fabricates clients, research, or execution results.

## Stack

| Layer        | Choice                                                                 |
|--------------|------------------------------------------------------------------------|
| Frontend     | Next.js + TypeScript + Tailwind CSS (Phase 7), dark responsive UI      |
| Backend      | Python 3.12 + FastAPI                                                  |
| Orchestration| LangGraph-style state machine in-process (Phase 3–4); n8n optional for external workflows |
| Database     | SQLAlchemy 2 — SQLite by default (`apps/api/personal_os.db`); Postgres/Supabase via `DATABASE_URL` |
| AI           | Configurable cloud providers via env API keys + free fallback; model config separated from code; provider fallback chain |
| Automation   | Playwright for authorized browser automation only (later phases)       |
| Scheduling   | `scheduled_jobs` table + background workers (later phases)             |
| Deployment   | No Docker daemon in this environment → venv + uvicorn now; Docker files documented for later |

## Monorepo

```
personal-os/
  apps/api/   FastAPI backend (app/ package, tests/)
  apps/web/   Next.js frontend (Phase 7)
  docs/       this file and future guides
```

## Agents (seeded in the `agents` table)

| Key           | Role |
|---------------|------|
| master        | Orchestrator: understand → plan → delegate → monitor → verify → report |
| research      | Web research, competitor analysis, source verification, research reports |
| tasks         | Task creation, status, priorities, deadlines, pending-work tracking |
| communication | Authorized email reading, reply drafts, follow-ups |
| clients       | Client records, inquiry handling, complaint categorization, follow-ups |
| business      | Business research/planning, market analysis, operational reports |
| developer     | Code generation, websites/apps, debugging, tests, deploy configs |
| finance       | Income/expense tracking from authorized records, invoices, summaries — **never executes payments** |
| marketing     | SEO research, content planning, social drafts, campaign analysis |
| projects      | Project monitoring, milestones, blockers, history |
| reporting     | Daily/weekly/monthly reports, agent & task completion reports |

All specialist agents communicate with the Master Agent through structured
inputs/outputs (task + task_steps rows, JSON payloads).

## Command execution engine (Phase 4)

```
USER COMMAND → UNDERSTANDING → OBJECTIVE → PLANNING → AGENT SELECTION
→ EXECUTION → VERIFICATION → DATABASE UPDATE → FINAL REPORT
```

Task states: `PENDING, PLANNING, RUNNING, WAITING_FOR_APPROVAL, COMPLETED,
FAILED, CANCELLED`. Every task has a UUID, description, assigned agent,
priority, timestamps, logs, result, and error fields.

## Permission tiers (Phase 9, modelled from Phase 2)

- **AUTOMATIC** — research, reading authorized files, creating reports,
  managing internal tasks, preparing email drafts, organizing projects.
- **APPROVAL_REQUIRED** — sending external email, publishing, submitting
  forms, changing important account settings, sharing files externally,
  contacting new clients. (Creates an `approvals` row; task waits in
  `WAITING_FOR_APPROVAL`.)
- **ALWAYS_MANUAL** — money transfers, financial transactions, password
  disclosure, irreversible account deletion. The system never performs these.

Security: JWT auth (bcrypt password hashing), role field on users, audit trail
in `activity_logs`, secrets only from environment, rate limits and error
monitoring in later phases. The system never bypasses CAPTCHAs or access
restrictions, and never treats webpage/document content as system instructions.

## Database (Phase 2 — implemented)

16 tables: `users, agents, conversations, messages, memories, tasks,
task_steps, projects, clients, files, reports, integrations, permissions,
approvals, activity_logs, scheduled_jobs`. UUID primary keys, foreign keys,
indexes on status/owner/foreign-key columns, JSON columns for flexible
payloads (logs, metadata, schedules).

### Migrations note (Alembic-free)

For this personal, single-user deployment, tables are auto-created on startup
via `Base.metadata.create_all` (idempotent). Schema evolution rule: additive
changes (new tables/columns with defaults) are safe with `create_all`; for
destructive changes, export the SQLite file, edit models, re-import — or point
`DATABASE_URL` at Postgres/Supabase and adopt Alembic at that point (the models
are Alembic-compatible; no Alembic dependency is carried until it is needed).

## 10-phase plan

1. **Project initialization & architecture** — ✅ monorepo, docs, env template
2. **Database & authentication** — ✅ models, JWT auth, agent + admin seeding
3. **Master AI Agent** — command understanding (EN + Roman Urdu), planning, provider chain with fallback
4. **Command execution engine** — task lifecycle, background execution, retry, verification gate
5. **Persistent memory** — preferences, instructions, project/task history, summaries; inspect/correct/delete APIs
6. **Specialist agents** — the 10 agents wired to real tools (research, tasks, files, reports…)
7. **Dashboard & interfaces** — Next.js, 13 pages, Command Center first
8. **External integrations** — Gmail/Calendar/Drive/GitHub connection screens (OAuth; never fake-connected)
9. **Security & permissions** — 3-tier enforcement, approvals UI, audit logs, rate limits
10. **Testing, optimization & deployment** — unit + e2e tests, health checks, production runbook

## Dashboard pages (Phase 7)

Overview, AI Command Center, Agent Management, Task Management, Project
Management, Client Management, Research Workspace, File Management, Reports &
Analytics, Memory Management, Integrations, Security & Permissions, Settings.
