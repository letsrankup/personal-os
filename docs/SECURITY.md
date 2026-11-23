# PERSONAL OS — Security & Permissions (Phase 9)

## Permission tiers

Every action the system can take belongs to exactly one tier (seeded in the
`permissions` table, visible to owner/admin users via `GET /permissions`
and the dashboard's Security page):

**AUTOMATIC** — the Master Agent may do these without asking:
research, reading authorized files, creating reports, managing internal
tasks, preparing email drafts, organizing project information.

**APPROVAL_REQUIRED** — an `approvals` row is created and the task waits in
`WAITING_FOR_APPROVAL` until the owner decides; nothing executes before
approval: sending external email, publishing websites or content,
submitting forms, changing important account settings, sharing files
externally, contacting new clients.

**ALWAYS_MANUAL** — the system refuses outright and never automates these,
even with approval:
- Money transfers and any financial transaction (the Finance Agent only
  records and totals entries; it never moves money).
- Password or secret disclosure.
- Irreversible account deletion.
- Other high-impact sensitive actions of the same kind.

The system never bypasses website security, CAPTCHAs, paywalls or access
restrictions, and never treats instructions found in webpages or documents
as system instructions.

## Authentication & roles

- Passwords are hashed with bcrypt; JWT bearer tokens (HS256) expire after
  `JWT_EXPIRE_MINUTES` (default 1440). Set a real `JWT_SECRET` in the
  environment for any real use — the shipped default is a dev placeholder.
- **Password policy:** registration requires at least 8 characters
  (rejected with HTTP 422 otherwise).
- **Roles:** `users.role` defaults to `owner` (single-user deployment);
  the seeded admin (created only from `ADMIN_EMAIL`/`ADMIN_PASSWORD` env)
  is `admin`. Owner/admin-only endpoints: `GET /permissions` and
  `POST /integrations/{key}/check` — any other role gets 403. All other
  endpoints accept any authenticated user and stay scoped to that user's
  own data (memories, tasks, projects, files, activity).

## Rate limits

In-memory, per client IP, fixed 60-second windows; exceeding a limit
returns HTTP 429 with an explanatory message:

| Bucket | Endpoints | Default | Env override |
|---|---|---|---|
| auth | `POST /auth/login`, `POST /auth/register` | 10 / min | `RATE_LIMIT_AUTH_PER_MIN` |
| commands | `POST /commands` | 60 / min | `RATE_LIMIT_COMMANDS_PER_MIN` |

Counters are process-local (fine for the single-instance personal
deployment); restart clears them.

## Audit log (`activity_logs`)

Written for: registration (`auth.register`), login success (`auth.login`)
**and failure** (`auth.login_failed`, with the attempted email), command
execution steps (orchestrator), approval decisions
(`approval.approved` / `approval.rejected`), task cancellation, memory
create/update/delete, integration checks (`integration.check` with the
resulting status), and scheduled-job lifecycle (`job.created`,
`job.executed`, `job.failed`, `job.deleted`). Users can read their own
trail via `GET /activity`; the dashboard's Security page shows it.

## Secrets handling

- All secrets (AI keys, GitHub token, Google client secret, Supabase keys,
  JWT secret) come from the environment / `apps/api/.env` only. None are
  hardcoded, none are committed (`.env` is git-ignored), and none are
  written to the database.
- Integration `config` stored in the DB contains only non-secret display
  data (login names, model names, HTTP statuses, notes, OAuth URLs). API
  responses additionally pass config through a masking filter that replaces
  any sensitive-looking key with `***`.
- Integration checks make the minimum possible external contact: GitHub
  verifies the token with one `GET /user`; Supabase is probed with one
  REST request; OpenAI/Gemini checks are presence-only and make **no** API
  call; Google checks only build an authorization URL — the OAuth consent
  and code exchange are always the user's manual step.

## CORS

The API only accepts browser calls from the origins in `ALLOWED_ORIGINS`
(comma-separated env; default `http://localhost:3000`). It is never
configured wide open.

## Scheduled jobs

The background scheduler only runs job kinds that exist (`report`); a job
creates real reports from live database counts and logs every execution.
Jobs never send email, publish, or perform any APPROVAL_REQUIRED or
ALWAYS_MANUAL action.
