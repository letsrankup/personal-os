"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import type { TokenOut, User } from "@/lib/types";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api<User>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, name }),
      });
      const tok = await api<TokenOut>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(tok.access_token);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
        <h1 className="text-lg font-semibold text-zinc-50">PERSONAL OS</h1>
        <p className="mb-5 text-sm text-zinc-400">Create your account</p>
        {error ? <div className="mb-3 rounded-lg bg-red-500/10 p-3 text-sm text-red-200">{error}</div> : null}
        <label className="mb-1 block text-xs text-zinc-400">Name</label>
        <input
          type="text" value={name} onChange={(e) => setName(e.target.value)}
          className="mb-3 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500"
        />
        <label className="mb-1 block text-xs text-zinc-400">Email</label>
        <input
          type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          className="mb-3 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500"
        />
        <label className="mb-1 block text-xs text-zinc-400">Password (min 8 characters)</label>
        <input
          type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500"
        />
        <button disabled={busy} className="w-full rounded-lg bg-zinc-100 py-2 text-sm font-medium text-zinc-900 disabled:opacity-50">
          {busy ? "Creating account…" : "Register"}
        </button>
        <p className="mt-4 text-center text-xs text-zinc-500">
          Already registered? <Link href="/login" className="text-zinc-300 underline">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
