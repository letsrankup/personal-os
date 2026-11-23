"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { JobRunResult, Report, ScheduledJob } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle, fmtDate } from "@/components/ui";

function JobsSection({ onRan }: { onRan: () => void }) {
  const [jobs, setJobs] = useState<ScheduledJob[] | null>(null);
  const [name, setName] = useState("");
  const [reportKind, setReportKind] = useState("summary");
  const [interval, setInterval] = useState("daily");
  const [busy, setBusy] = useState<string | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [jobMsg, setJobMsg] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    setJobs(await api<ScheduledJob[]>("/jobs"));
  }, []);

  useEffect(() => {
    loadJobs().catch((e: Error) => setJobError(e.message));
  }, [loadJobs]);

  async function createJob(ev: React.FormEvent) {
    ev.preventDefault();
    setJobError(null);
    setJobMsg(null);
    try {
      await api<ScheduledJob>("/jobs", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), kind: "report", report_kind: reportKind, interval }),
      });
      setName("");
      await loadJobs();
      setJobMsg("Job created — it will run on schedule, or use Run now.");
    } catch (e) {
      setJobError(e instanceof Error ? e.message : "Could not create job");
    }
  }

  async function runJob(job: ScheduledJob) {
    setBusy(job.id);
    setJobError(null);
    setJobMsg(null);
    try {
      const res = await api<JobRunResult>(`/jobs/${job.id}/run`, { method: "POST" });
      await loadJobs();
      onRan();
      setJobMsg(
        res.executed
          ? `“${job.name}” ran — a new ${job.report_kind} report was created.`
          : `“${job.name}” failed: ${res.error ?? "unknown error"}`,
      );
    } catch (e) {
      setJobError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setBusy(null);
    }
  }

  async function deleteJob(job: ScheduledJob) {
    if (!window.confirm(`Delete scheduled job “${job.name}”?`)) return;
    setJobError(null);
    try {
      await api<void>(`/jobs/${job.id}`, { method: "DELETE" });
      await loadJobs();
    } catch (e) {
      setJobError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <Card className="mb-5">
      <div className="font-medium text-zinc-50">Scheduled report jobs</div>
      <p className="mt-0.5 text-xs text-zinc-500">
        Jobs run the Reporting Agent on schedule (GET/POST /jobs) and create real reports. One-off and
        missed runs are never back-filled silently — check Last run below.
      </p>
      {jobError ? (
        <div className="mt-3">
          <ErrorBox message={jobError} />
        </div>
      ) : null}
      {jobMsg ? <div className="mt-3 text-sm text-emerald-300">{jobMsg}</div> : null}
      {!jobs ? (
        <Loading />
      ) : jobs.length === 0 ? (
        <div className="mt-3 text-sm text-zinc-500">No scheduled jobs yet — create one below.</div>
      ) : (
        <div className="mt-3 space-y-2">
          {jobs.map((j) => (
            <div key={j.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-800 px-3 py-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-zinc-100">{j.name}</div>
                <div className="text-xs text-zinc-500">
                  {j.report_kind} report · every {j.interval} · {j.enabled ? "enabled" : "disabled"} · last run{" "}
                  {fmtDate(j.last_run_at)} · next run {fmtDate(j.next_run_at)}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => runJob(j)}
                  disabled={busy === j.id}
                  className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"
                >
                  {busy === j.id ? "Running…" : "Run now"}
                </button>
                <button
                  onClick={() => deleteJob(j)}
                  className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-red-300 hover:bg-zinc-800"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      <form onSubmit={createJob} className="mt-4 flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs text-zinc-400">
          Job name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="e.g. Morning summary"
            className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-400">
          Report kind
          <select value={reportKind} onChange={(e) => setReportKind(e.target.value)} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm">
            <option value="summary">summary</option>
            <option value="daily">daily</option>
            <option value="weekly">weekly</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-zinc-400">
          Interval
          <select value={interval} onChange={(e) => setInterval(e.target.value)} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm">
            <option value="daily">daily</option>
            <option value="weekly">weekly</option>
          </select>
        </label>
        <button type="submit" className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 hover:bg-white">
          Create job
        </button>
      </form>
    </Card>
  );
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[] | null>(null);
  const [kind, setKind] = useState("");
  const [selected, setSelected] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setReports(await api<Report[]>(`/reports${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`));
  }, [kind]);

  useEffect(() => {
    load().catch((e: Error) => setError(e.message));
  }, [load]);

  const kinds = Array.from(new Set((reports ?? []).map((r) => r.kind))).sort();

  function download(r: Report) {
    const blob = new Blob([r.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${r.kind}-${r.title.replace(/[^a-z0-9]+/gi, "-").slice(0, 60) || "report"}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (error) return <ErrorBox message={error} />;

  return (
    <div>
      <PageTitle title="Reports & Analytics" sub="Reports generated by the Reporting, Business and Marketing agents (GET /reports)" />
      <JobsSection onRan={() => load().catch(() => undefined)} />
      <div className="mb-4 flex gap-2">
        <select value={kind} onChange={(e) => setKind(e.target.value)} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm">
          <option value="">All kinds</option>
          {["summary", "daily", "weekly", "business", "marketing"].map((k) => <option key={k} value={k}>{k}</option>)}
          {kinds.filter((k) => !["summary", "daily", "weekly", "business", "marketing"].includes(k)).map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
      </div>
      {!reports ? (
        <Loading />
      ) : reports.length === 0 ? (
        <Empty message="No reports of this kind yet. Generate one in the Command Center, e.g. “Generate a daily report”." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
          <div className="space-y-2">
            {reports.map((r) => (
              <button key={r.id} onClick={() => setSelected(r)} className={`w-full rounded-xl border p-3 text-left ${selected?.id === r.id ? "border-zinc-500 bg-zinc-800/70" : "border-zinc-800 bg-zinc-900/60 hover:bg-zinc-900"}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium text-zinc-100">{r.title}</span>
                  <Badge value={r.kind} />
                </div>
                <div className="mt-1 text-xs text-zinc-500">{fmtDate(r.created_at)}</div>
              </button>
            ))}
          </div>
          <div>
            {selected ? (
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="font-medium text-zinc-50">{selected.title}</div>
                    <div className="mt-0.5 text-xs text-zinc-500">
                      kind: {selected.kind} · {fmtDate(selected.created_at)}
                      {selected.period_start ? ` · period ${fmtDate(selected.period_start)} → ${fmtDate(selected.period_end)}` : ""}
                    </div>
                  </div>
                  <button onClick={() => download(selected)} className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-200 hover:bg-zinc-800">
                    Download
                  </button>
                </div>
                <pre className="mt-3 whitespace-pre-wrap text-sm text-zinc-200">{selected.content}</pre>
              </Card>
            ) : (
              <Empty message="Select a report to view its full content." />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
