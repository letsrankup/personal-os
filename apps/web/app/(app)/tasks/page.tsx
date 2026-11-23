"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Task, TaskDetail } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle, fmtDate } from "@/components/ui";

const STATUSES = ["", "PENDING", "PLANNING", "RUNNING", "WAITING_FOR_APPROVAL", "COMPLETED", "FAILED", "CANCELLED"];

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [status, setStatus] = useState("");
  const [agent, setAgent] = useState("");
  const [agents, setAgents] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<TaskDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (agent) params.set("agent", agent);
    const qs = params.toString();
    setTasks(await api<Task[]>(`/tasks${qs ? `?${qs}` : ""}`));
  }, [status, agent]);

  useEffect(() => {
    load().catch((e: Error) => setError(e.message));
  }, [load]);

  useEffect(() => {
    api<Task[]>("/tasks")
      .then((rows) => setAgents(Array.from(new Set(rows.map((t) => t.agent_key))).sort()))
      .catch(() => undefined);
  }, []);

  async function toggle(id: string) {
    if (expanded?.id === id) {
      setExpanded(null);
      return;
    }
    try {
      setExpanded(await api<TaskDetail>(`/tasks/${id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load task");
    }
  }

  async function cancel(id: string) {
    try {
      await api(`/tasks/${id}/cancel`, { method: "POST" });
      setExpanded(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cancel failed");
    }
  }

  if (error) return <ErrorBox message={error} />;

  return (
    <div>
      <PageTitle title="Task Management" sub="Every task the Master Agent planned and executed (GET /tasks)" />
      <div className="mb-4 flex flex-wrap gap-2">
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {STATUSES.filter(Boolean).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={agent} onChange={(e) => setAgent(e.target.value)} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm">
          <option value="">All agents</option>
          {agents.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>
      {!tasks ? (
        <Loading />
      ) : tasks.length === 0 ? (
        <Empty message="No tasks match these filters." />
      ) : (
        <div className="space-y-2">
          {tasks.map((t) => (
            <Card key={t.id} className="p-3">
              <button onClick={() => toggle(t.id)} className="flex w-full flex-wrap items-center gap-2 text-left">
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-zinc-100">{t.title || t.description}</span>
                <Badge value={t.status} />
                <span className="text-xs text-zinc-500">{t.agent_key}</span>
                <span className="text-xs text-zinc-500">{t.priority}</span>
                <span className="text-xs text-zinc-500">{fmtDate(t.created_at)}</span>
              </button>
              {expanded?.id === t.id ? (
                <div className="mt-3 space-y-2 border-t border-zinc-800 pt-3 text-sm">
                  <p className="whitespace-pre-wrap text-zinc-300">{expanded.description}</p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
                    <span>Tier: {expanded.permission_tier}</span>
                    <span>Verified: {expanded.verified ? "yes" : "no"}</span>
                    <span>Started: {fmtDate(expanded.started_at)}</span>
                    <span>Completed: {fmtDate(expanded.completed_at)}</span>
                  </div>
                  {expanded.result ? <div className="rounded-lg bg-zinc-800/60 p-3 whitespace-pre-wrap text-zinc-200">{expanded.result}</div> : null}
                  {expanded.error ? <div className="rounded-lg bg-red-500/10 p-3 whitespace-pre-wrap text-red-200">{expanded.error}</div> : null}
                  {expanded.steps.length > 0 ? (
                    <div>
                      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">Steps</div>
                      <ol className="space-y-1">
                        {expanded.steps.map((s) => (
                          <li key={s.id} className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                            <span className="text-zinc-500">{s.order}.</span>
                            <span className="flex-1">{s.description}</span>
                            <Badge value={s.status} />
                            {s.error ? <span className="text-red-300">{s.error}</span> : null}
                          </li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                  {expanded.logs.length > 0 ? (
                    <div>
                      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">Execution log</div>
                      <ul className="space-y-0.5 text-xs text-zinc-500">
                        {expanded.logs.map((l, i) => <li key={i}>[{l.level ?? "info"}] {l.message ?? ""}</li>)}
                      </ul>
                    </div>
                  ) : null}
                  {!["COMPLETED", "FAILED", "CANCELLED"].includes(expanded.status) ? (
                    <button onClick={() => cancel(expanded.id)} className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs font-medium text-red-200 hover:bg-red-500/30">
                      Cancel task
                    </button>
                  ) : null}
                </div>
              ) : null}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
