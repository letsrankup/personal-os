"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import type { TokenOut } from "@/lib/types";
import { CoreMark } from "@/components/Sidebar";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const tok = await api<TokenOut>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(tok.access_token);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="glass glass-glow w-full max-w-sm rounded-3xl p-6">
        <div className="mb-4 flex items-center gap-3">
          <CoreMark size={42} />
          <div>
            <h1 className="font-display text-base font-bold tracking-[0.18em] text-zinc-50">
              PERSONAL <span className="text-cyan-300 text-glow">OS</span>
            </h1>
            <p className="text-xs text-zinc-400">Sign in to your AI Command Center</p>
          </div>
        </div>
        {error ? <div className="mb-3 rounded-lg bg-red-500/10 p-3 text-sm text-red-200">{error}</div> : null}
        <label className="mb-1 block text-xs text-zinc-400">Email</label>
        <input
          type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          className="mb-3 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-cyan-300/50"
        />
        <label className="mb-1 block text-xs text-zinc-400">Password</label>
        <input
          type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-cyan-300/50"
        />
        <button disabled={busy} className="w-full rounded-xl border border-cyan-300/40 bg-cyan-400/15 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/25 disabled:opacity-50">
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="mt-4 text-center text-xs text-zinc-500">
          No account? <Link href="/register" className="text-zinc-300 underline">Register</Link>
        </p>
      </form>
    </div>
  );
}
