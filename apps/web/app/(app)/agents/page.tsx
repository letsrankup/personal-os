"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle } from "@/components/ui";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Agent[]>("/agents").then(setAgents).catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!agents) return <Loading />;

  return (
    <div>
      <PageTitle title="Agent Management" sub="Specialist agents registered with the Master Agent (live from GET /agents)" />
      {agents.length === 0 ? (
        <Empty message="No agents registered." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {agents.map((a) => (
            <Card key={a.id}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-zinc-50">{a.name}</div>
                  <div className="text-xs text-zinc-500">key: {a.key}</div>
                </div>
                <Badge value={a.status} />
              </div>
              <p className="mt-2 text-sm text-zinc-400">{a.role}</p>
              <p className="mt-2 text-xs text-zinc-500">Model: {a.model ?? "provider default"}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
