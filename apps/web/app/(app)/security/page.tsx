"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Activity, Permission } from "@/lib/types";
import { Card, Empty, ErrorBox, Loading, PageTitle, fmtDate } from "@/components/ui";

const TIERS: { key: string; label: string; desc: string; cls: string }[] = [
  { key: "AUTOMATIC", label: "Automatic", desc: "The system may do these without asking.", cls: "border-emerald-500/30" },
  { key: "APPROVAL_REQUIRED", label: "Approval required", desc: "Held for your decision in the Command Center before anything runs.", cls: "border-amber-500/30" },
  { key: "ALWAYS_MANUAL", label: "Always manual", desc: "Never executed by the system — refused automatically.", cls: "border-red-500/30" },
];

export default function SecurityPage() {
  const [perms, setPerms] = useState<Permission[] | null>(null);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Permission[]>("/permissions").then(setPerms).catch((e: Error) => setError(e.message));
    api<Activity[]>("/activity?limit=50").then(setActivity).catch(() => undefined);
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!perms) return <Loading />;

  return (
    <div>
      <PageTitle title="Security & Permissions" sub="The three permission tiers enforced by the orchestrator (GET /permissions) and the audit log (GET /activity)" />
      <div className="grid gap-3 lg:grid-cols-3">
        {TIERS.map((t) => {
          const rows = perms.filter((p) => p.tier === t.key);
          return (
            <Card key={t.key} className={t.cls}>
              <div className="font-semibold text-zinc-50">{t.label}</div>
              <p className="mb-3 mt-0.5 text-xs text-zinc-500">{t.desc}</p>
              {rows.length === 0 ? (
                <p className="text-xs text-zinc-500">No actions in this tier.</p>
              ) : (
                <ul className="space-y-2">
                  {rows.map((p) => (
                    <li key={p.id} className="border-b border-white/5 pb-2 last:border-0">
                      <div className="font-mono text-sm text-zinc-100">{p.action}</div>
                      {p.description ? <div className="text-xs text-zinc-400">{p.description}</div> : null}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          );
        })}
      </div>

      <h2 className="mb-2 mt-8 text-sm font-semibold text-zinc-200">Audit log — recent activity</h2>
      {activity.length === 0 ? (
        <Empty message="No activity recorded for your account yet." />
      ) : (
        <Card className="p-0">
          <ul className="divide-y divide-white/5/60">
            {activity.map((a) => (
              <li key={a.id} className="flex flex-wrap items-baseline gap-x-3 px-4 py-2 text-sm">
                <span className="text-zinc-200">{a.action}</span>
                <span className="text-zinc-500">actor: {a.actor}</span>
                {a.entity ? <span className="text-zinc-500">{a.entity}</span> : null}
                {Object.keys(a.details).length > 0 ? (
                  <span className="max-w-full truncate font-mono text-[11px] text-zinc-600">{JSON.stringify(a.details)}</span>
                ) : null}
                <span className="ml-auto text-xs text-zinc-500">{fmtDate(a.created_at)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
