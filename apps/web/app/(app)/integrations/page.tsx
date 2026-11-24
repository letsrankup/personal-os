"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Integration } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle, fmtDate } from "@/components/ui";

function cfgStr(cfg: Record<string, unknown>, key: string): string | null {
  const v = cfg?.[key];
  return typeof v === "string" && v ? v : null;
}

export default function IntegrationsPage() {
  const [rows, setRows] = useState<Integration[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(await api<Integration[]>("/integrations"));
  }, []);

  useEffect(() => {
    load().catch((e: Error) => setError(e.message));
  }, [load]);

  async function check(provider: string) {
    setChecking(provider);
    setCheckError(null);
    try {
      const updated = await api<Integration>(`/integrations/${provider}/check`, { method: "POST" });
      setRows((prev) => (prev ?? []).map((r) => (r.provider === provider ? updated : r)));
    } catch (e) {
      setCheckError(e instanceof Error ? e.message : "Check failed");
    } finally {
      setChecking(null);
    }
  }

  if (error) return <ErrorBox message={error} />;
  if (!rows) return <Loading />;

  return (
    <div>
      <PageTitle
        title="Integrations"
        sub="Status comes from the API (GET /integrations) and only changes when a real check runs — “Check status” calls POST /integrations/{provider}/check. Nothing is ever shown as connected without a check proving it. Setup steps: docs/INTEGRATIONS.md."
      />
      {checkError ? (
        <div className="mb-3">
          <ErrorBox message={`Check failed: ${checkError}`} />
        </div>
      ) : null}
      {rows.length === 0 ? (
        <Empty message="No integrations registered." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {rows.map((r) => {
            const note = cfgStr(r.config, "note");
            const login = cfgStr(r.config, "login");
            const model = cfgStr(r.config, "model");
            const authUrl = cfgStr(r.config, "auth_url");
            const reason = cfgStr(r.config, "reason");
            const httpStatus = r.config?.["http_status"];
            return (
              <Card key={r.provider}>
                <div className="flex items-start justify-between gap-2">
                  <div className="font-medium capitalize text-zinc-50">{r.provider.replace(/_/g, " ")}</div>
                  <Badge value={r.status} />
                </div>
                <div className="mt-2 space-y-0.5 text-sm text-zinc-400">
                  <div>Account: {r.account_label ?? login ?? "—"}</div>
                  {model ? <div>Model: {model}</div> : null}
                  {typeof httpStatus === "number" ? <div>Last HTTP status: {httpStatus}</div> : null}
                  <div>Last checked: {fmtDate(r.last_checked_at)}</div>
                  {note ? <div className="text-xs text-zinc-500">{note}</div> : null}
                  {reason ? <div className="text-xs text-red-300">{reason}</div> : null}
                  {authUrl ? (
                    <div className="pt-1">
                      <a
                        href={authUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-sky-300 underline underline-offset-2 hover:text-sky-200"
                      >
                        Open Google authorization page
                      </a>
                      <div className="text-xs text-zinc-500">
                        Completing OAuth is a manual step — the app never finishes it for you.
                      </div>
                    </div>
                  ) : null}
                </div>
                <button
                  onClick={() => check(r.provider)}
                  disabled={checking === r.provider}
                  className="mt-3 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-zinc-200 hover:bg-white/[0.06] disabled:opacity-50"
                >
                  {checking === r.provider ? "Checking…" : "Check status"}
                </button>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
