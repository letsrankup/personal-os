"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Agent, Memory, Overview } from "@/lib/types";
import { Card, Empty, ErrorBox, Loading, PageTitle, SectionLabel, Stat, fmtDate } from "@/components/ui";
import AICore from "@/components/AICore";
import { usePolling } from "@/lib/usePolling";

const Brain3D = dynamic(() => import("@/components/Brain3D"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center">
      <AICore state="THINKING" size={170} />
    </div>
  ),
});

export default function BrainPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [webgl, setWebgl] = useState<boolean | null>(null);

  useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      setWebgl(Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl")));
    } catch {
      setWebgl(false);
    }
  }, []);

  const refresh = useCallback(() => {
    api<Overview>("/overview").then(setOverview).catch((e: Error) => setError(e.message));
    api<Agent[]>("/agents").then(setAgents).catch(() => undefined);
    api<Memory[]>("/memories").then(setMemories).catch(() => undefined);
  }, []);

  usePolling(refresh, 12000);

  if (error && !overview) return <ErrorBox message={error} />;
  if (!overview) return <Loading label="Loading neural interface…" />;

  const activeAgents = agents.filter((a) => a.status === "active");
  const activity = overview.running_tasks > 0 ? 1.7 : 1;
  const recentMemories = [...memories].slice(0, 5);

  return (
    <div className="space-y-4">
      <PageTitle
        title="AI Brain"
        sub="Interactive 3D neural core — two hemispheres, 720 nodes, live connections. Rotation speed follows real running tasks. Drag to look around."
      />

      <div className="glass glass-glow relative overflow-hidden rounded-3xl">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(700px_380px_at_50%_0%,rgba(124,58,237,0.13),transparent_70%)]" />
        <div className="relative h-[380px] md:h-[540px]">
          {webgl === false ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
              <AICore state={overview.running_tasks > 0 ? "EXECUTING" : "IDLE"} size={210} />
              <p className="max-w-sm text-sm text-zinc-400">
                This device does not expose WebGL, so the lightweight 2D core is shown instead. All live data below is real.
              </p>
            </div>
          ) : (
            <Brain3D activity={activity} />
          )}
        </div>
        <div className="relative flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-white/5 px-5 py-3 text-xs text-zinc-400">
          <span>
            <span className="text-cyan-300">●</span> Neural nodes: 720
          </span>
          <span>
            <span className="text-violet-300">●</span> Energy particles: 240
          </span>
          <span>
            Neural speed: <span className="text-zinc-200">{overview.running_tasks > 0 ? "ELEVATED — tasks running" : "cruise"}</span>
          </span>
          <span className="ml-auto hidden md:inline">Drag to rotate · Touch supported</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Active agents" value={`${activeAgents.length} / ${agents.length || 11}`} accent="text-violet-300" />
        <Stat label="Running tasks" value={overview.running_tasks} accent="text-sky-300" />
        <Stat label="Memories stored" value={memories.length} accent="text-cyan-200" hint="visualized in the neural core" />
        <Stat label="Completed tasks" value={overview.completed_tasks} accent="text-emerald-300" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <SectionLabel>Memory visualization — latest stored</SectionLabel>
          <div className="mt-3">
            {recentMemories.length === 0 ? (
              <Empty message="No memories stored yet — tell the Master Agent: “Yaad rakho ke …”" />
            ) : (
              <ul className="space-y-2 text-sm">
                {recentMemories.map((m) => (
                  <li key={m.id} className="flex items-baseline justify-between gap-3 border-b border-white/5 pb-2 last:border-0">
                    <span className="min-w-0">
                      <span className="text-zinc-200">{m.title}</span>{" "}
                      <span className="text-xs text-zinc-500">[{m.kind}]</span>
                    </span>
                    <span className="shrink-0 text-xs text-zinc-500">{fmtDate(m.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
        <Card>
          <SectionLabel>Live agent activity</SectionLabel>
          <div className="mt-3">
            {overview.recent_activity.length === 0 ? (
              <Empty message="No activity recorded yet." />
            ) : (
              <ul className="space-y-2 text-sm">
                {overview.recent_activity.slice(0, 6).map((a, i) => (
                  <li key={i} className="flex items-baseline justify-between gap-3 border-b border-white/5 pb-2 last:border-0">
                    <span className="min-w-0">
                      <span className="text-zinc-200">{a.action}</span>{" "}
                      <span className="text-zinc-500">
                        by {a.actor}
                        {a.entity ? ` · ${a.entity}` : ""}
                      </span>
                    </span>
                    <span className="shrink-0 text-xs text-zinc-500">{fmtDate(a.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
