"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Client } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle, fmtDate } from "@/components/ui";

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Client[]>("/clients").then(setClients).catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!clients) return <Loading />;

  return (
    <div>
      <PageTitle title="Client Management" sub="Clients managed by the Clients Agent (GET /clients)" />
      {clients.length === 0 ? (
        <Empty message="No clients yet. Add one from the Command Center, e.g. “Add client Acme Traders”." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {clients.map((c) => {
            const inquiries = Array.isArray(c.meta?.inquiries) ? (c.meta.inquiries as unknown[]) : [];
            return (
              <Card key={c.id}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium text-zinc-50">{c.name}</div>
                    <div className="text-xs text-zinc-500">{c.category}</div>
                  </div>
                  <Badge value={c.status} />
                </div>
                <div className="mt-2 space-y-0.5 text-sm text-zinc-400">
                  {c.company ? <div>Company: {c.company}</div> : null}
                  {c.email ? <div>Email: {c.email}</div> : null}
                  {c.phone ? <div>Phone: {c.phone}</div> : null}
                </div>
                {c.notes ? (
                  <p className="mt-2 max-h-32 overflow-y-auto whitespace-pre-wrap rounded-lg bg-zinc-800/50 p-2 text-xs text-zinc-400">{c.notes}</p>
                ) : null}
                <div className="mt-2 flex gap-x-4 text-xs text-zinc-500">
                  <span>Inquiries logged: {inquiries.length}</span>
                  <span>Updated {fmtDate(c.updated_at)}</span>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
