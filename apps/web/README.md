# PERSONAL OS — Web Dashboard (Phase 7)

Next.js (App Router) + TypeScript + Tailwind CSS dashboard wired to the
FastAPI backend. Every page renders real API data — no mock data.

## Run

```bash
# 1) API (from apps/api):  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# 2) Web (from apps/web):
cp .env.example .env.local   # NEXT_PUBLIC_API_URL, default http://localhost:8000
npm install
npm run dev                  # or: npm run build && npm run start
```

Open http://localhost:3000 — register or sign in; unauthenticated visits
redirect to /login. Pages: Overview, Command Center, Agents, Tasks,
Projects, Clients, Research, Files, Reports, Memory, Integrations,
Security & Permissions, Settings.
