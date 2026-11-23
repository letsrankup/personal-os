"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Memory } from "@/lib/types";
import { Card, Empty, ErrorBox, Loading, PageTitle, fmtDate } from "@/components/ui";

export default function ResearchPage() {
  const [items, setItems] = useState<Memory[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Memory[]>("/memories?kind=research").then(setItems).catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!items) return <Loading />;

  return (
    <div>
      <PageTitle title="Research Workspace" sub="Findings saved by the Research Agent as research memories (GET /memories?kind=research)" />
      {items.length === 0 ? (
        <Empty message="No research yet. Ask in the Command Center, e.g. “Research electric bikes in Pakistan”." />
      ) : (
        <div className="space-y-3">
          {items.map((m) => (
            <Card key={m.id}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div className="font-medium text-zinc-50">{m.title || "Research"}</div>
                <div className="text-xs text-zinc-500">{fmtDate(m.created_at)}</div>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-300">{m.content}</p>
              {m.tags.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-1">
                  {m.tags.map((t, i) => (
                    <span key={i} className="rounded-full border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-400">{t}</span>
                  ))}
                </div>
              ) : null}
              {m.source_ref ? <div className="mt-2 text-xs text-zinc-500">Source: {m.source_ref}</div> : null}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
