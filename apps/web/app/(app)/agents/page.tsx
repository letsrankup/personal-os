"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Activity, Agent, Task } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle, SectionLabel, fmtDate } from "@/components/ui";
import { usePolling } from "@/lib/usePolling";

const IDENTITY: Record<string, { color: string; glyph: string }> = {
  master: { color: "#22d3ee", glyph: "M" },
  research: { color: "#a78bfa", glyph: "R" },
  tasks: { color: "#38bdf8", glyph: "T" },
  communication: { color: "#34d399", glyph: "C" },
  clients: { color: "#fbbf24", glyph: "CL" },
  business: { color: "#f472b6", glyph: "B" },
  developer: { color: "#818cf8", glyph: "D" },
  finance: { color: "#4ade80", glyph: "F" },
  marketing: { color: "#fb923c", glyph: "MK" },
  projects: { color: "#2dd4bf", glyph: "P" },
  reporting: { color: "#e879f9", glyph: "RP" },
};

function identity(key: string) {
  return IDENTITY[key] ?? { color: "#94a3b8", glyph: key.slice(0, 2).toUpperCase() };
}

interface Workload {
  total: number;
  running: number;
  completed: number;
  failed: number;
  current: Task | null;
}

export default function AgentNetworkPage() {
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("master");

  const refresh = useCallback(() => {
    api<Agent[]>("/agents").then(setAgents).catch((e: Error) => setError(e.message));
    api<Task[]>("/tasks").then(setTasks).catch(() => undefined);
    api<Activity[]>("/activity?limit=60").then(setActivity).catch(() => undefined);
  }, []);

  usePolling(refresh, 15000);

  const workload = useMemo(() => {
    const map = new Map<string, Workload>();
    for (const t of tasks) {
      const w = map.get(t.agent_key) ?? { total: 0, running: 0, completed: 0, failed: 0, current: null };
      w.total++;
      if (t.status === "RUNNING" || t.status === "PLANNING") {
        w.running++;
        w.current = t;
      }
      if (t.status === "COMPLETED") w.completed++;
      if (t.status === "FAILED") w.failed++;
      map.set(t.agent_key, w);
    }
    return map;
  }, [tasks]);

  if (error && !agents) return <ErrorBox message={error} />;
  if (!agents) return <Loading label="Loading agent network…" />;

  const master = agents.find((a) => a.key === "master");
  const specialists = agents.filter((a) => a.key !== "master");
  const sel = agents.find((a) => a.key === selected) ?? master;
  const selWork = sel ? workload.get(sel.key) : undefined;
  const selTasks = sel ? tasks.filter((t) => t.agent_key === sel.key).slice(0, 5) : [];
  const selActivity = sel
    ? activity.filter((a) => a.actor === sel.key || a.actor.endsWith(sel.key) || a.actor.includes(sel.key)).slice(0, 5)
    : [];

  const CX = 320;
  const CY = 205;
  const RX = 252;
  const RY = 148;

  return (
    <div className="space-y-4">
      <PageTitle
        title="Agent Network"
        sub="Master Agent connected to every specialist. Lines light up while that agent has a task running — all status is live from the API."
      />

      {/* Network map */}
      <div className="glass glass-glow overflow-hidden rounded-3xl">
        <svg viewBox="0 0 640 410" className="block h-auto w-full" role="img" aria-label="Agent network map">
          <defs>
            <radialGradient id="hub" cx="50%" cy="42%" r="65%">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
              <stop offset="40%" stopColor="#22d3ee" />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.3" />
            </radialGradient>
          </defs>
          {specialists.map((a, i) => {
            const angle = (i / Math.max(specialists.length, 1)) * Math.PI * 2 - Math.PI / 2;
            const x = CX + RX * Math.cos(angle);
            const y = CY + RY * Math.sin(angle);
            const w = workload.get(a.key);
            const busyAgent = (w?.running ?? 0) > 0;
            return (
              <line
                key={`line-${a.key}`}
                x1={CX}
                y1={CY}
                x2={x}
                y2={y}
                stroke={identity(a.key).color}
                strokeOpacity={busyAgent ? 0.85 : 0.28}
                strokeWidth={busyAgent ? 1.8 : 1.1}
                className={busyAgent ? "energy-dash" : undefined}
              />
            );
          })}
          {/* master hub */}
          <g onClick={() => master && setSelected(master.key)} className="cursor-pointer">
            <circle cx={CX} cy={CY} r="46" fill="none" stroke="#22d3ee" strokeOpacity="0.35" strokeDasharray="3 6" />
            <circle cx={CX} cy={CY} r="33" fill="url(#hub)" />
            <text x={CX} y={CY + 5} textAnchor="middle" fontSize="15" fontWeight="700" fill="#04202b">
              M
            </text>
            <text x={CX} y={CY + 66} textAnchor="middle" fontSize="11" fill="#e2e8f0" fontWeight="600">
              Master Agent
            </text>
          </g>
          {specialists.map((a, i) => {
            const angle = (i / Math.max(specialists.length, 1)) * Math.PI * 2 - Math.PI / 2;
            const x = CX + RX * Math.cos(angle);
            const y = CY + RY * Math.sin(angle);
            const id = identity(a.key);
            const isSel = selected === a.key;
            return (
              <g key={a.key} onClick={() => setSelected(a.key)} className="cursor-pointer">
                {isSel ? <circle cx={x} cy={y} r="27" fill="none" stroke={id.color} strokeOpacity="0.7" strokeWidth="1.4" /> : null}
                <circle cx={x} cy={y} r="20" fill="#0a0f1e" stroke={id.color} strokeWidth="1.6" />
                <circle cx={x} cy={y} r="20" fill={id.color} opacity="0.14" />
                <text x={x} y={y + 4} textAnchor="middle" fontSize="10.5" fontWeight="700" fill={id.color}>
                  {id.glyph}
                </text>
                <text x={x} y={y + 38} textAnchor="middle" fontSize="10" fill="#cbd5e1">
                  {a.name.replace(" Agent", "")}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Agent cards */}
      {agents.length === 0 ? (
        <Empty message="No agents registered." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {agents.map((a) => {
            const id = identity(a.key);
            const w = workload.get(a.key);
            const isSel = selected === a.key;
            return (
              <button key={a.id} onClick={() => setSelected(a.key)} className="text-left">
                <Card className={`h-full transition ${isSel ? "glass-glow" : "hover:border-cyan-200/20"}`}>
                  <div className="flex items-start gap-3">
                    <span
                      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full font-display text-sm font-bold"
                      style={{ color: id.color, border: `1.5px solid ${id.color}`, background: `${id.color}1f`, boxShadow: `0 0 16px -4px ${id.color}` }}
                    >
                      {id.glyph}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium text-zinc-50">{a.name}</span>
                        <Badge value={a.status} />
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-[13px] leading-snug text-zinc-400">{a.role}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
                    <span>
                      Tasks: <span className="text-zinc-200">{w?.total ?? 0}</span>
                    </span>
                    <span>
                      Running: <span className="text-sky-300">{w?.running ?? 0}</span>
                    </span>
                    <span>
                      Done: <span className="text-emerald-300">{w?.completed ?? 0}</span>
                    </span>
                    <span>
                      Failed: <span className="text-red-300">{w?.failed ?? 0}</span>
                    </span>
                  </div>
                  {w?.current ? <p className="mt-2 truncate text-xs text-sky-200/80">▶ Now: {w.current.title}</p> : null}
                </Card>
              </button>
            );
          })}
        </div>
      )}

      {/* Selected agent workspace */}
      {sel ? (
        <Card className="glass-glow">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className="flex h-12 w-12 items-center justify-center rounded-full font-display text-base font-bold"
              style={{
                color: identity(sel.key).color,
                border: `1.5px solid ${identity(sel.key).color}`,
                background: `${identity(sel.key).color}1f`,
                boxShadow: `0 0 18px -4px ${identity(sel.key).color}`,
              }}
            >
              {identity(sel.key).glyph}
            </span>
            <div className="min-w-0">
              <div className="font-display text-sm font-bold uppercase tracking-[0.16em] text-zinc-50">{sel.name} — Workspace</div>
              <div className="text-xs text-zinc-500">
                key: {sel.key} · model: {sel.model ?? "provider default"}
              </div>
            </div>
            <span className="ml-auto">
              <Badge value={sel.status} />
            </span>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-zinc-300">{sel.role}</p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <SectionLabel>Recent tasks</SectionLabel>
              {selTasks.length === 0 ? (
                <p className="mt-2 text-sm text-zinc-500">No tasks yet for this agent.</p>
              ) : (
                <ul className="mt-2 space-y-2 text-sm">
                  {selTasks.map((t) => (
                    <li key={t.id} className="flex items-center justify-between gap-3 border-b border-white/5 pb-2 last:border-0">
                      <span className="min-w-0 truncate text-zinc-200">{t.title}</span>
                      <Badge value={t.status} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <SectionLabel>Activity history</SectionLabel>
              {selActivity.length === 0 ? (
                <p className="mt-2 text-sm text-zinc-500">No recorded activity for this agent yet.</p>
              ) : (
                <ul className="mt-2 space-y-2 text-sm">
                  {selActivity.map((a) => (
                    <li key={a.id} className="flex items-baseline justify-between gap-3 border-b border-white/5 pb-2 last:border-0">
                      <span className="min-w-0 text-zinc-300">
                        {a.action}
                        {a.entity ? <span className="text-zinc-500"> · {a.entity}</span> : null}
                      </span>
                      <span className="shrink-0 text-xs text-zinc-500">{fmtDate(a.created_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <div className="mt-3 text-xs text-zinc-500">
            Workload so far: {selWork?.total ?? 0} tasks · {selWork?.completed ?? 0} completed · {selWork?.failed ?? 0} failed
          </div>
        </Card>
      ) : null}
    </div>
  );
}
