"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle, fmtDate } from "@/components/ui";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Project[]>("/projects").then(setProjects).catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!projects) return <Loading />;

  return (
    <div>
      <PageTitle title="Project Management" sub="Progress is computed from real linked tasks (GET /projects)" />
      {projects.length === 0 ? (
        <Empty message="No projects yet. Create one from the Command Center, e.g. “Create project Website Revamp”." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {projects.map((p) => (
            <Card key={p.id}>
              <div className="flex items-start justify-between gap-2">
                <div className="font-medium text-zinc-50">{p.name}</div>
                <Badge value={p.status} />
              </div>
              {p.description ? <p className="mt-1 whitespace-pre-wrap text-sm text-zinc-400">{p.description}</p> : null}
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-800">
                <div className="h-full bg-emerald-500" style={{ width: `${p.progress_pct}%` }} />
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 text-xs text-zinc-500">
                <span>{p.completed_tasks}/{p.total_tasks} tasks completed</span>
                <span>{p.progress_pct}%</span>
                <span>Updated {fmtDate(p.updated_at)}</span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
