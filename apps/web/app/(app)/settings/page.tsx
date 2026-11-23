"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import type { Health } from "@/lib/types";
import { Card, PageTitle } from "@/components/ui";

export default function SettingsPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setHealth((await r.json()) as Health);
      })
      .catch((e: Error) => setHealthError(e.message));
  }, []);

  return (
    <div>
      <PageTitle title="Settings" sub="Runtime configuration of this dashboard" />
      <div className="grid gap-3 md:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-sm font-semibold text-zinc-200">API connection</h2>
          <div className="space-y-1 text-sm text-zinc-400">
            <div>API base URL in use: <span className="font-mono text-zinc-100">{API_URL}</span></div>
            <div className="text-xs text-zinc-500">Set via NEXT_PUBLIC_API_URL at build/run time (see apps/web/.env.example).</div>
          </div>
        </Card>
        <Card>
          <h2 className="mb-2 text-sm font-semibold text-zinc-200">API health (live GET /health)</h2>
          {health ? (
            <div className="space-y-1 text-sm text-zinc-400">
              <div>Status: <span className={health.status === "ok" ? "text-emerald-300" : "text-red-300"}>{health.status}</span></div>
              <div>Service: <span className="text-zinc-100">{health.service}</span></div>
              <div>Database: <span className="text-zinc-100">{health.db}</span></div>
              {health.ai_provider ? <div>AI provider (first in fallback chain): <span className="text-zinc-100">{health.ai_provider}</span></div> : null}
            </div>
          ) : healthError ? (
            <div className="text-sm text-red-300">Health check failed: {healthError}. Is the API running at {API_URL}?</div>
          ) : (
            <div className="text-sm text-zinc-400">Checking…</div>
          )}
        </Card>
        <Card className="md:col-span-2">
          <h2 className="mb-2 text-sm font-semibold text-zinc-200">AI model configuration</h2>
          <p className="text-sm text-zinc-400">
            Model API keys are configured <span className="text-zinc-100">server-side only</span>, via environment
            variables on the API (<span className="font-mono">OPENAI_API_KEY</span>,{" "}
            <span className="font-mono">GEMINI_API_KEY</span>, optional <span className="font-mono">AI_PROVIDER</span>,{" "}
            <span className="font-mono">OPENAI_MODEL</span> / <span className="font-mono">GEMINI_MODEL</span>). They are
            never entered or stored in this dashboard. With no keys set, the API falls back to the free endpoint and
            then to its clearly-labelled offline mode.
          </p>
        </Card>
      </div>
    </div>
  );
}
