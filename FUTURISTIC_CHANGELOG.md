# FUTURISTIC TRANSFORMATION — CHANGELOG (24 Nov 2026)

Branch: `futuristic-ui` · Backup: branch `backup-pre-futuristic-2026-11-24` (pre-change `main`).
Goal: JARVIS-style command center + VisionOS glassmorphism + 3D AI Brain, without touching
existing features, API contracts, database schema, or authentication.

## Design system
- `apps/web/app/globals.css` — rewritten: deep-space background gradients, `.glass` / `.glass-glow`
  panels, glow/gradient text, AI-core keyframes (spin, pulse, energy dash, ping ring), custom
  scrollbars, `prefers-reduced-motion` support.
- `apps/web/app/layout.tsx` — Orbitron (display) + Inter (body) via next/font, theme-color viewport.
- `apps/web/components/ui.tsx` — Card/Stat/Badge/Loading restyled as glass; new shared `inputCls`,
  `btnCls`, `btnGhostCls`, `SectionLabel`. All existing exports/signatures preserved.
- `apps/web/components/Sidebar.tsx` — glass sidebar with animated core logo, per-section SVG icons,
  active-state glow, mobile top bar with collapsible menu; added **AI Brain** and **Finance** links.
- `apps/web/components/PageTransition.tsx` — NEW: Framer Motion page transitions (respects reduced motion).
- `apps/web/app/(app)/layout.tsx` — page-transition wrapper, glowing boot loader, wider content column.

## Command Center (home)
- `apps/web/app/(app)/page.tsx` — rebuilt: live API/DB/AI health pill, hero with the animated
  **AI Core** and a quick-command box (English/Roman Urdu + voice). Core states
  (IDLE/LISTENING/THINKING/PLANNING/EXECUTING/VERIFYING/COMPLETED/ERROR) are driven only by real
  request lifecycle + live `/overview` data — never simulated. Auto-refresh every 15s.
- `apps/web/components/AICore.tsx` — NEW: state-driven SVG core component.
- `apps/web/lib/usePolling.ts` — NEW: visibility-aware polling hook.

## 3D AI Brain
- `apps/web/components/Brain3D.tsx` — NEW: Three.js / React Three Fiber brain — 720 neural nodes in
  two hemispheres, proximity connections, 240 orbiting energy particles, drag/touch rotation,
  DPR capped for mobile. Rotation speed follows real running tasks.
- `apps/web/app/(app)/brain/page.tsx` — NEW page: 3D canvas in a glass stage, WebGL fallback to the
  2D core, live stats, latest memories (memory visualization), live activity feed.

## Agent Network
- `apps/web/app/(app)/agents/page.tsx` — rebuilt as a network room: SVG map (Master hub connected to
  all specialists; a link animates while that agent has a RUNNING/PLANNING task), per-agent identity
  colors/glyphs, workload counts from real `/tasks`, and a per-agent workspace (recent tasks +
  activity history from `/activity`).

## AI Workspace
- `apps/web/app/(app)/command/page.tsx` — restyled glass chat; mini AI Core in the header mirrors the
  real status of the last command; conversations, approvals and voice input unchanged in behavior.

## Finance (new screen + one additive API endpoint)
- `apps/api/app/main.py` — NEW read-only `GET /finance` (auth required, optional `kind` filter,
  limit ≤ 500). No existing endpoint changed.
- `apps/api/app/schemas.py` — NEW `FinanceEntryOut` schema.
- `apps/web/app/(app)/finance/page.tsx` — NEW page: income/expense/net stats, Recharts 14-day
  income-vs-expense bars, expense-by-category pie, latest entries — all computed from real rows.
- `apps/web/lib/types.ts` — NEW `FinanceEntry` type.

## Restyled (visual only, behavior unchanged)
- tasks, projects, clients, research, reports, memory, integrations, security pages — legacy zinc
  surfaces/buttons replaced with the glass system.
- `apps/web/app/login/page.tsx`, `app/register/page.tsx` — glass cards with animated core logo.

## Dependencies added (all free / open-source)
- `three`, `@react-three/fiber`, `framer-motion`, `recharts` (+ `@types/three` dev).

## Verification (local, before merge)
- API test suite: **62/62 passed**.
- `GET /finance` round-trip: command → expense recorded → endpoint returned the exact row; 401 without auth.
- Web production build: **passed**; all 17 routes returned HTTP 200 in a local smoke test.

## Known remaining gaps (honest)
- No dedicated Marketing screen — no marketing data source exists in the backend; marketing work
  runs through AI Workspace commands and shows in Research/Memory/Reports.
- Real-time updates use smart polling (15s) — Vercel serverless has no persistent WebSocket/SSE
  channel for this API; statuses are still always backend-confirmed.
- The free AI provider (Pollinations, no key) can still return template-like answers for open-ended
  questions; structured work (finance, tasks, memory, reports) is unaffected.
