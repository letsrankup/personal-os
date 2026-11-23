# PERSONAL OS — Integrations Setup Guide (Phase 8)

Every integration starts as `not_connected`. A status only changes when a
**real check** runs (`POST /integrations/{key}/check`, owner/admin only, or
the "Check status" button on the dashboard's Integrations page). Statuses:
`not_connected` · `connected` · `awaiting_oauth` · `error`. Secrets are read
from the API's environment at check time — they are **never** stored in the
database and **never** returned by the API (only logins, model names, HTTP
statuses and notes are).

## Where to put values

The API reads its environment from the process env, falling back to
`apps/api/.env` (copy the template: `cp .env.example apps/api/.env`, then
restart the API). Never commit a real `.env`.

| Service | Env vars | What "connected" means |
|---|---|---|
| GitHub | `GITHUB_TOKEN` | Live `GET https://api.github.com/user` returned 200; your GitHub login is shown |
| OpenAI | `OPENAI_API_KEY` (+ optional `OPENAI_MODEL`) | Key present (presence check only — no API call is made) |
| Google Gemini | `GEMINI_API_KEY` (+ optional `GEMINI_MODEL`) | Key present (presence check only) |
| Supabase | `SUPABASE_URL`, `SUPABASE_ANON_KEY` | `{SUPABASE_URL}/rest/v1/` answered over HTTP (200/401/404 all prove reachability; the status code is recorded) |
| Gmail | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (+ `APP_BASE_URL`) | `awaiting_oauth` + an authorization URL — **you** complete the consent in a browser |
| Google Calendar | same Google vars | same |
| Google Drive | same Google vars | same |

---

## GitHub

1. GitHub → Settings → Developer settings → **Personal access tokens** →
   Fine-grained tokens → *Generate new token*.
2. Give it read access to the repositories PERSONAL OS should see (no admin
   or write scopes are needed for the connection check).
3. Put it in the API environment: `GITHUB_TOKEN=<the token>`.
4. Restart the API, then run **Check status** for GitHub. A 200 response
   marks it `connected` and shows your GitHub login. A rejected token shows
   `error` with the HTTP status (usually 401) — the token itself is never
   displayed or stored.

## OpenAI / Gemini (AI model keys)

1. OpenAI: platform.openai.com → API keys → create a key.
   Gemini: Google AI Studio (aistudio.google.com) → *Get API key*.
2. Put `OPENAI_API_KEY=…` and/or `GEMINI_API_KEY=…` in the API environment.
   Optionally set `OPENAI_MODEL` / `GEMINI_MODEL` (defaults
   `gpt-4o-mini` / `gemini-2.0-flash`).
3. Check status → `connected` with the model name shown. The check is
   presence-only: it makes **no** API call, so it costs nothing. The same
   keys also power the AI provider chain used by the agents.

## Supabase

1. supabase.com → your project → Settings → **API**: copy the **Project URL**
   and the **anon public** key (not the service_role key — PERSONAL OS never
   needs it for this check).
2. Put `SUPABASE_URL=https://<project>.supabase.co` and
   `SUPABASE_ANON_KEY=<anon key>` in the API environment.
3. Check status → the REST endpoint is probed; any HTTP response marks it
   `connected` and records the status code. A network failure shows `error`
   with the reason.
4. To use Supabase Postgres as the app's database itself, set
   `DATABASE_URL=postgresql+psycopg://…` instead (see `.env.example`) —
   that is separate from this integration check.

## Google services (Gmail / Calendar / Drive) — OAuth

These need **your own** Google Cloud OAuth client. Until both values exist,
all three honestly show `not_connected` with the note *"Requires Google
OAuth credentials — see docs/INTEGRATIONS.md"*. PERSONAL OS never completes
OAuth for you and never asks for your Google password.

1. Go to console.cloud.google.com and create (or pick) a project.
2. **APIs & Services → Library**: enable the **Gmail API**, **Google
   Calendar API** and **Google Drive API**.
3. **APIs & Services → OAuth consent screen**: choose *External* (or
   *Internal* for a Workspace account), fill in the app name, and add your
   own Google account under **Test users** while the app is in testing.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   → type **Web application**. Under **Authorized redirect URIs** add:
   `<APP_BASE_URL>/integrations/google/callback`
   (with the default `APP_BASE_URL=http://localhost:8000` that is
   `http://localhost:8000/integrations/google/callback`).
5. Put the resulting values in the API environment:
   `GOOGLE_CLIENT_ID=…`, `GOOGLE_CLIENT_SECRET=…`, and `APP_BASE_URL` if the
   API is not on `http://localhost:8000`.
6. Restart the API and run **Check status** for Gmail / Calendar / Drive:
   the status becomes `awaiting_oauth` and the Integrations page shows an
   **authorization URL** built from your client ID with the service's
   scopes (Gmail: read + send; Calendar: read-only; Drive: read-only).
7. Open that URL yourself and complete Google's consent screen. Exchanging
   the returned code for tokens is **not** automated in Phase 8 — until a
   token-exchange step is built, the services remain `awaiting_oauth` and
   agents that need Gmail keep failing honestly ("Gmail integration not
   connected") rather than pretending to send or read mail.

## Troubleshooting

- Status stays `not_connected` after setting a variable → the API was not
  restarted, or the variable is in the wrong file (it belongs in the API's
  environment / `apps/api/.env`, not the web app's).
- GitHub `error` with HTTP 401 → token expired, revoked, or mistyped.
- Supabase `error` with a network reason → wrong URL or the project is
  paused (free-tier projects pause after inactivity; open the Supabase
  dashboard to resume it).
