"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, API_URL } from "@/lib/api";
import type { CommandOut, Health, Overview } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, SectionLabel, Stat, btnCls, fmtDate, inputCls } from "@/components/ui";
import AICore, { type CoreState } from "@/components/AICore";
import { usePolling } from "@/lib/usePolling";

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  start: () => void;
  onresult: ((e: { results: { 0: { 0: { transcript: string } } } }) => void) | null;
  onend: (() => void) | null;
}

export default function CommandCenterPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cmd, setCmd] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [coreOverride, setCoreOverride] = useState<CoreState | null>(null);
  const [lastReply, setLastReply] = useState<CommandOut | null>(null);
  const [cmdError, setCmdError] = useState<string | null>(null);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(() => {
    api<Overview>("/overview")
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
    fetch(`${API_URL}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => undefined);
  }, []);

  usePolling(refresh, 15000);

  useEffect(() => () => {
    if (resetTimer.current) clearTimeout(resetTimer.current);
  }, []);

  const coreState: CoreState =
    coreOverride ??
    (listening ? "LISTENING" : busy ? "THINKING" : data && data.running_tasks > 0 ? "EXECUTING" : "IDLE");

  async function runCommand(e: React.FormEvent) {
    e.preventDefault();
    const text = cmd.trim();
    if (!text || busy) return;
    setBusy(true);
    setCmdError(null);
    setCoreOverride("THINKING");
    try {
      const out = await api<CommandOut>("/commands", {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      setLastReply(out);
      setCmd("");
      setCoreOverride(
        out.status === "COMPLETED"
          ? "COMPLETED"
          : out.status === "FAILED"
            ? "ERROR"
            : out.status === "WAITING_FOR_APPROVAL"
              ? "PLANNING"
              : "EXECUTING",
      );
      refresh();
      if (resetTimer.current) clearTimeout(resetTimer.current);
      resetTimer.current = setTimeout(() => setCoreOverride(null), 5000);
    } catch (err) {
      setCmdError(err instanceof Error ? err.message : "Command failed");
      setCoreOverride("ERROR");
      if (resetTimer.current) clearTimeout(resetTimer.current);
      resetTimer.current = setTimeout(() => setCoreOverride(null), 5000);
    } finally {
      setBusy(false);
    }
  }

  function voiceInput() {
    const w = window as unknown as {
      SpeechRecognition?: new () => SpeechRecognitionLike;
      webkitSpeechRecognition?: new () => SpeechRecognitionLike;
    };
    const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!Ctor) {
      setCmdError("Voice input is not supported in this browser.");
      return;
    }
    const rec = new Ctor();
    rec.lang = "ur-PK";
    rec.interimResults = false;
    rec.onresult = (e) => setCmd((prev) => `${prev} ${e.results[0][0].transcript}`.trim());
    rec.onend = () => setListening(false);
    setListening(true);
    rec.start();
  }

  if (error && !data) return <ErrorBox message={error} />;
  if (!data) return <Loading label="Booting command center…" />;

  const healthOk = health?.status === "ok" && health?.db === "ok";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="font-display text-xl font-bold uppercase tracking-[0.14em] md:text-2xl">
            <span className="text-gradient">Command Center</span>
          </h1>
          <p className="mt-0.5 text-sm text-zinc-400">Your autonomous AI employee — live system view, refreshed automatically.</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${
              healthOk
                ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-300"
                : "border-amber-400/30 bg-amber-500/10 text-amber-300"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${healthOk ? "animate-blink bg-emerald-300" : "bg-amber-300"}`} />
            {health ? `API ${health.status} · DB ${health.db} · AI ${health.ai_provider ?? "—"}` : "API status unknown"}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-300/20 bg-cyan-400/5 px-3 py-1.5 text-xs text-cyan-200">
            <span className="h-1.5 w-1.5 animate-blink rounded-full bg-cyan-300" /> LIVE
          </span>
        </div>
      </div>

      {/* Hero: AI Core + quick command */}
      <div className="glass glass-glow relative overflow-hidden rounded-3xl">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(600px_300px_at_50%_-10%,rgba(34,211,238,0.14),transparent_70%)]" />
        <div className="relative grid items-center gap-4 p-5 md:grid-cols-[auto_1fr] md:gap-8 md:p-7">
          <div className="mx-auto animate-float-y">
            <AICore state={coreState} size={215} />
          </div>
          <div className="min-w-0">
            <SectionLabel>Master Agent — Quick Command</SectionLabel>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-zinc-400">
              Give a command in English or Roman Urdu. The core reacts to the real backend state — thinking while the
              Master Agent works, completed only when the API confirms it.
            </p>
            <form onSubmit={runCommand} className="mt-4 flex flex-col gap-2 sm:flex-row">
              <input
                value={cmd}
                onChange={(e) => setCmd(e.target.value)}
                placeholder="e.g. Kharcha 2500 petrol · Meri pending tasks list karo · Generate a summary report"
                className={inputCls}
                aria-label="Quick command"
              />
              <div className="flex gap-2">
                <button type="button" onClick={voiceInput} className={btnCls} title="Voice command" aria-label="Voice command">
                  {listening ? "● Listening" : "🎤 Voice"}
                </button>
                <button type="submit" disabled={busy} className={btnCls}>
                  {busy ? "Working…" : "Execute"}
                </button>
              </div>
            </form>
            {cmdError ? <p className="mt-2 text-sm text-red-300">{cmdError}</p> : null}
            {lastReply ? (
              <div className="mt-3 rounded-2xl border border-cyan-200/10 bg-black/25 p-3.5 text-sm">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <Badge value={lastReply.status} />
                  <span className="text-xs text-zinc-400">
                    agent: <span className="text-zinc-200">{lastReply.agent}</span> · task {lastReply.task_id.slice(0, 8)}…
                  </span>
                  {lastReply.approval_id ? (
                    <Link href="/command" className="text-xs font-medium text-amber-300 hover:underline">
                      Approval needed → open AI Workspace
                    </Link>
                  ) : null}
                </div>
                <p className="whitespace-pre-wrap leading-relaxed text-zinc-200">{lastReply.reply}</p>
              </div>
            ) : null}
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <Link href="/brain" className="rounded-full border border-violet-300/25 bg-violet-400/10 px-3 py-1.5 text-violet-200 transition hover:bg-violet-400/20">
                Open 3D AI Brain →
              </Link>
              <Link href="/command" className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-zinc-300 transition hover:border-cyan-300/30 hover:text-cyan-100">
                Full AI Workspace →
              </Link>
              <Link href="/agents" className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-zinc-300 transition hover:border-cyan-300/30 hover:text-cyan-100">
                Agent Network →
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Total tasks" value={data.total_tasks} />
        <Stat label="Completed" value={data.completed_tasks} accent="text-emerald-300" />
        <Stat label="Running" value={data.running_tasks} accent="text-sky-300" />
        <Stat label="Failed" value={data.failed_tasks} accent="text-red-300" />
        <Stat label="Active agents" value={data.active_agents} accent="text-violet-300" hint="of 11 specialists + master" />
        <Stat label="Projects in progress" value={data.projects_in_progress} />
        <Stat label="Pending" value={data.tasks_by_status["PENDING"] ?? 0} />
        <Stat label="Waiting approval" value={data.tasks_by_status["WAITING_FOR_APPROVAL"] ?? 0} accent="text-amber-300" />
      </div>

      {/* Activity + reports */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-200">Live agent activity</h2>
            <span className="h-1.5 w-1.5 animate-blink rounded-full bg-cyan-300" />
          </div>
          {data.recent_activity.length === 0 ? (
            <Empty message="No activity recorded yet." />
          ) : (
            <ul className="space-y-2 text-sm">
              {data.recent_activity.map((a, i) => (
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
        </Card>
        <Card>
          <h2 className="mb-3 font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-200">Latest reports</h2>
          {data.latest_reports.length === 0 ? (
            <Empty message="No reports yet — ask the Reporting Agent for one in the AI Workspace." />
          ) : (
            <ul className="space-y-2 text-sm">
              {data.latest_reports.map((r) => (
                <li key={r.id} className="flex items-baseline justify-between gap-3 border-b border-white/5 pb-2 last:border-0">
                  <span className="min-w-0 truncate">
                    <Link href="/reports" className="text-zinc-200 hover:text-cyan-200 hover:underline">
                      {r.title}
                    </Link>{" "}
                    <Badge value={r.kind} />
                  </span>
                  <span className="shrink-0 text-xs text-zinc-500">{fmtDate(r.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
