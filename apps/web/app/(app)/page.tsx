"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Overview } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle, Stat, fmtDate } from "@/components/ui";

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Overview>("/overview").then(setData).catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;

  return (
    <div>
      <PageTitle title="Overview" sub="Live counts from the PERSONAL OS API" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Total tasks" value={data.total_tasks} />
        <Stat label="Completed" value={data.completed_tasks} accent="text-emerald-300" />
        <Stat label="Running" value={data.running_tasks} accent="text-sky-300" />
        <Stat label="Failed" value={data.failed_tasks} accent="text-red-300" />
        <Stat label="Active agents" value={data.active_agents} />
        <Stat label="Projects in progress" value={data.projects_in_progress} />
        <Stat label="Pending" value={data.tasks_by_status["PENDING"] ?? 0} />
        <Stat label="Waiting approval" value={data.tasks_by_status["WAITING_FOR_APPROVAL"] ?? 0} accent="text-amber-300" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-zinc-200">Recent activity</h2>
          {data.recent_activity.length === 0 ? (
            <Empty message="No activity recorded yet." />
          ) : (
            <ul className="space-y-2 text-sm">
              {data.recent_activity.map((a, i) => (
                <li key={i} className="flex items-baseline justify-between gap-3 border-b border-zinc-800/60 pb-2 last:border-0">
                  <span className="min-w-0">
                    <span className="text-zinc-200">{a.action}</span>{" "}
                    <span className="text-zinc-500">by {a.actor}{a.entity ? ` · ${a.entity}` : ""}</span>
                  </span>
                  <span className="shrink-0 text-xs text-zinc-500">{fmtDate(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-zinc-200">Latest reports</h2>
          {data.latest_reports.length === 0 ? (
            <Empty message="No reports yet — ask the Reporting Agent for one in the Command Center." />
          ) : (
            <ul className="space-y-2 text-sm">
              {data.latest_reports.map((r) => (
                <li key={r.id} className="flex items-baseline justify-between gap-3 border-b border-zinc-800/60 pb-2 last:border-0">
                  <span className="min-w-0 truncate">
                    <Link href="/reports" className="text-zinc-200 hover:underline">{r.title}</Link>{" "}
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
