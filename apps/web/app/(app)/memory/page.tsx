"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Memory } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle, fmtDate } from "@/components/ui";

const KINDS = ["preference", "instruction", "project", "task", "conversation_summary", "research", "decision", "file_ref"];

export default function MemoryPage() {
  const [items, setItems] = useState<Memory[] | null>(null);
  const [q, setQ] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({ kind: "preference", title: "", content: "", tags: "" });
  const [editing, setEditing] = useState<Memory | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (kindFilter) params.set("kind", kindFilter);
    const qs = params.toString();
    setItems(await api<Memory[]>(`/memories${qs ? `?${qs}` : ""}`));
  }, [q, kindFilter]);

  useEffect(() => {
    load().catch((e: Error) => setError(e.message));
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/memories", {
        method: "POST",
        body: JSON.stringify({
          kind: form.kind,
          title: form.title,
          content: form.content,
          tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
        }),
      });
      setForm({ kind: "preference", title: "", content: "", tags: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/memories/${editing.id}`, {
        method: "PATCH",
        body: JSON.stringify({ kind: editing.kind, title: editing.title, content: editing.content, tags: editing.tags }),
      });
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this memory permanently?")) return;
    try {
      await api(`/memories/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div>
      <PageTitle title="Memory Management" sub="Persistent memory the agents retrieve before follow-up commands (GET/POST/PATCH/DELETE /memories)" />
      {error ? <div className="mb-3"><ErrorBox message={error} /></div> : null}

      <Card className="mb-4">
        <h2 className="mb-3 text-sm font-semibold text-zinc-200">Add a memory</h2>
        <form onSubmit={create} className="grid gap-2 md:grid-cols-[160px_1fr]">
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm">
            {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Title" className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500" />
          <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} required placeholder="Content (required)" rows={3} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500 md:col-span-2" />
          <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="Tags, comma separated" className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500" />
          <button disabled={busy} className="rounded-lg bg-zinc-100 py-2 text-sm font-medium text-zinc-900 disabled:opacity-50">Save memory</button>
        </form>
      </Card>

      <div className="mb-4 flex flex-wrap gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search memories (title / content / tags)…" className="min-w-52 flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500" />
        <select value={kindFilter} onChange={(e) => setKindFilter(e.target.value)} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm">
          <option value="">All kinds</option>
          {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
      </div>

      {!items ? (
        <Loading />
      ) : items.length === 0 ? (
        <Empty message="No memories match." />
      ) : (
        <div className="space-y-2">
          {items.map((m) => (
            <Card key={m.id}>
              {editing?.id === m.id ? (
                <form onSubmit={saveEdit} className="grid gap-2">
                  <div className="flex flex-wrap gap-2">
                    <select value={editing.kind} onChange={(e) => setEditing({ ...editing, kind: e.target.value })} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm">
                      {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
                    </select>
                    <input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} className="min-w-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500" />
                  </div>
                  <textarea value={editing.content} onChange={(e) => setEditing({ ...editing, content: e.target.value })} rows={4} className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500" />
                  <input value={editing.tags.join(", ")} onChange={(e) => setEditing({ ...editing, tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) })} placeholder="Tags, comma separated" className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500" />
                  <div className="flex gap-2">
                    <button disabled={busy} className="rounded-lg bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-900 disabled:opacity-50">Save</button>
                    <button type="button" onClick={() => setEditing(null)} className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300">Cancel</button>
                  </div>
                </form>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex-1 text-sm font-medium text-zinc-100">{m.title || "(untitled)"}</span>
                    <Badge value={m.kind} />
                    <span className="text-xs text-zinc-500">{fmtDate(m.updated_at)}</span>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-zinc-400">{m.content}</p>
                  {m.tags.length > 0 ? <div className="mt-1 text-xs text-zinc-500">tags: {m.tags.join(", ")}</div> : null}
                  {m.source_ref ? <div className="text-xs text-zinc-500">source: {m.source_ref}</div> : null}
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => setEditing(m)} className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-200 hover:bg-zinc-800">Edit</button>
                    <button onClick={() => remove(m.id)} className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs font-medium text-red-200 hover:bg-red-500/30">Delete</button>
                  </div>
                </>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
