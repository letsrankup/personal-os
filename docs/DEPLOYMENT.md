# PERSONAL OS — Deployment Guide

How to run PERSONAL OS locally, with Docker, and in production.
This is a **private, personal-use system** — deploy it for one user, not as a
public SaaS.

> Honest note: Docker is **not installed in the sandbox where this project was
> built**, so the Docker files (`apps/api/Dockerfile`, `apps/web/Dockerfile`,
> `docker-compose.yml`) are correct-by-construction but **untested in that
> sandbox**. Everything in section (a) is tested; the test suite (62 API
> tests) and the production web build pass — see `PROGRESS.md` and
> `FINAL_REPORT.md`.

---

## (a) Local run (tested)

Prerequisites: Python 3.12, Node.js 24 (any recent LTS works for local dev).

### API

```bash
cd apps/api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp ../../.env.example .env        # optional — sane local defaults exist
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Health: `GET http://127.0.0.1:8000/health` →
  `{"status":"ok","service":"personal-os-api","db":"ok","ai_provider":"…"}`
- Interactive docs: http://127.0.0.1:8000/docs
- The default database is SQLite at `apps/api/personal_os.db`; tables,
  agents (11) and permissions (14) are seeded automatically on startup.
- Optional admin user: set `ADMIN_EMAIL` + `ADMIN_PASSWORD` in the
  environment before first start (or run `.venv/bin/python -m app.seed`).

### Web dashboard

```bash
cd apps/web
npm ci
cp .env.example .env.local        # NEXT_PUBLIC_API_URL, default http://localhost:8000
npm run build
npm run start                     # http://localhost:3000
```

(For development, `npm run dev` works the same way.)

Then open http://localhost:3000, register an account, and use the Command
Center. The dashboard talks to the API from the **browser**, so
`NEXT_PUBLIC_API_URL` must be an address the browser can reach.

### Tests

```bash
cd apps/api && .venv/bin/python -m pytest -q     # 62 passed
```

---

## (b) Docker run

Prerequisites: Docker with the Compose plugin, on any machine.

```bash
cp .env.example .env              # fill in real secrets (see checklist below)
docker compose up --build
```

- Web: http://localhost:3000 — API: http://localhost:8000/health
- Services: `api` (uvicorn on 8000, non-root, `/health` healthcheck) and
  `web` (Next.js production server on 3000), `web` waits for a healthy `api`.
- Data: by default the API uses SQLite on the named volume `api-data`
  (`DATABASE_URL=sqlite:////app/data/personal_os.db` inside the container),
  so data survives container rebuilds. To use Postgres/Supabase instead,
  set `DATABASE_URL` in `.env` — your value overrides the default.
- Environment passthrough: the compose file forwards the documented env
  vars (JWT secret, origins, admin seed, AI keys, integration credentials)
  from your shell/`.env` into the `api` container. Nothing is baked into
  the images.
- `NEXT_PUBLIC_API_URL` is a **build-time** value for the web image (it is
  baked into the browser bundle). The compose default is
  `http://localhost:8000`, correct when the browser runs on the same
  machine as the containers. For a remote host, set it to the API's public
  URL **before** `docker compose up --build`.

Stop with `docker compose down` (add `-v` to also delete the SQLite volume).

---

## (c) Vercel deploy — web dashboard only

Vercel can host the **Next.js dashboard**. It cannot host the API (see (d)).

1. Push this repo to GitHub (see the git notes in `FINAL_REPORT.md`).
2. In Vercel: **Add New → Project → Import** the repository.
3. Set **Root Directory** to `apps/web`.
4. Framework preset: Next.js (auto-detected). Build command `npm run build`,
   install command `npm ci` (defaults are fine).
5. Environment variable: `NEXT_PUBLIC_API_URL` = the **public URL of your
   deployed API** (e.g. `https://api.yourdomain.com`). Without it the
   dashboard defaults to `http://localhost:8000`, which only works on your
   own machine.
6. Deploy. Then set the API's `ALLOWED_ORIGINS` to your Vercel domain
   (e.g. `https://personal-os-….vercel.app`) and restart the API, or the
   browser will block the dashboard's API calls (CORS).

---

## (d) API hosting options

**The API needs a persistent host.** Two reasons:

- The default database is a **local SQLite file** — serverless/ephemeral
  hosts would lose it on every restart.
- The **report scheduler runs as an in-process loop** (checks due jobs
  every 60 s). It only runs while the API process is alive, and rate
  limiting is likewise process-local. A single always-on instance is the
  supported shape.

Good fits:

- **Any VPS with Docker** (Hetzner, DigitalOcean, a home server, …):
  clone the repo, `cp .env.example .env`, fill in secrets,
  `docker compose up -d --build`. Put a reverse proxy (Caddy/Nginx) with
  HTTPS in front of ports 8000/3000. This is the recommended setup.
- **Render / Railway (Docker deploy)**: create a service from
  `apps/api/Dockerfile`, attach a **persistent disk** mounted at
  `/app/data`, set `DATABASE_URL=sqlite:////app/data/personal_os.db` (or a
  Postgres URL), set the env vars from the checklist below, and expose
  port 8000. Keep the service on an always-on (non-sleeping) plan —
  sleeping breaks the scheduler and makes the dashboard feel broken.
  Alternatively skip the web container there and host only the dashboard
  on Vercel per (c), pointing `NEXT_PUBLIC_API_URL` at the API service.

**Public dashboard rule:** if the dashboard is public (Vercel), the API
must be public too and reachable over HTTPS, and `NEXT_PUBLIC_API_URL`
must point at the deployed API — the browser calls the API directly.
There is no API proxying built into the dashboard.

---

## (e) Production checklist

- [ ] `JWT_SECRET` — long random value (e.g. `openssl rand -hex 32`).
      The code has a clearly-marked **dev default**; never run production
      with it.
- [ ] `ALLOWED_ORIGINS` — your dashboard origin(s), comma-separated
      (default `http://localhost:3000`).
- [ ] `ADMIN_EMAIL` / `ADMIN_PASSWORD` — set before first boot if you want
      a seeded admin (password ≥ 8 characters). Remove/rotate after use if
      desired; the seed is idempotent.
- [ ] AI keys (optional): `OPENAI_API_KEY` and/or `GEMINI_API_KEY`
      (+ `OPENAI_MODEL` / `GEMINI_MODEL`). With no keys the system uses the
      free fallback and then a clearly-labelled offline mode — functional,
      but answers are templates, not real AI output.
- [ ] `DATABASE_URL` — leave unset for SQLite-on-volume, or set a
      Postgres/Supabase URL (see `docs/INTEGRATIONS.md` for Supabase).
- [ ] Integration credentials as needed: `GITHUB_TOKEN`,
      `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`, `SUPABASE_URL` +
      `SUPABASE_ANON_KEY` — full walkthrough in `docs/INTEGRATIONS.md`.
- [ ] HTTPS in front of both services; firewall everything except the
      proxy ports.
- [ ] Backups: copy the SQLite file (or the `api-data` volume) / use your
      Postgres provider's backups.
- [ ] After deploy: `GET /health` shows `"db":"ok"`, register/login works,
      and `POST /integrations/{key}/check` from the Integrations page
      confirms each integration you configured.
