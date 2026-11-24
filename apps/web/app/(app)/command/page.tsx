"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Approval, CommandOut, Conversation, Message } from "@/lib/types";
import { Badge, Card, Empty, ErrorBox, PageTitle, btnCls, btnGhostCls, fmtDate, inputCls } from "@/components/ui";
import AICore, { type CoreState } from "@/components/AICore";

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  start: () => void;
  onresult: ((e: { results: { 0: { 0: { transcript: string } } } }) => void) | null;
  onend: (() => void) | null;
}

export default function CommandPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastResult, setLastResult] = useState<CommandOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async () => {
    const rows = await api<Conversation[]>("/conversations");
    setConversations(rows);
    return rows;
  }, []);

  const loadApprovals = useCallback(async () => {
    setApprovals(await api<Approval[]>("/approvals"));
  }, []);

  const loadMessages = useCallback(async (id: string) => {
    setMessages(await api<Message[]>(`/conversations/${id}/messages`));
  }, []);

  useEffect(() => {
    loadConversations()
      .then((rows) => {
        if (rows.length > 0) {
          setActiveId(rows[0].id);
          return loadMessages(rows[0].id);
        }
        return undefined;
      })
      .catch((e: Error) => setError(e.message));
    loadApprovals().catch(() => undefined);
  }, [loadConversations, loadApprovals, loadMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, lastResult]);

  async function selectConversation(id: string) {
    setActiveId(id);
    setLastResult(null);
    try {
      await loadMessages(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load messages");
    }
  }

  function newConversation() {
    setActiveId(null);
    setMessages([]);
    setLastResult(null);
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api<CommandOut>("/commands", {
        method: "POST",
        body: JSON.stringify({ text, conversation_id: activeId }),
      });
      setLastResult(out);
      setInput("");
      setActiveId(out.conversation_id);
      await loadMessages(out.conversation_id);
      await loadConversations();
      await loadApprovals();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Command failed");
    } finally {
      setBusy(false);
    }
  }

  async function decide(id: string, decision: "approved" | "rejected") {
    try {
      await api(`/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      });
      await loadApprovals();
      if (activeId) await loadMessages(activeId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    }
  }

  function voiceInput() {
    const w = window as unknown as { SpeechRecognition?: new () => SpeechRecognitionLike; webkitSpeechRecognition?: new () => SpeechRecognitionLike };
    const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!Ctor) {
      setError("Voice input is not supported in this browser.");
      return;
    }
    const rec = new Ctor();
    rec.lang = "ur-PK";
    rec.interimResults = false;
    rec.onresult = (e) => setInput((prev) => `${prev} ${e.results[0][0].transcript}`.trim());
    rec.onend = () => setListening(false);
    setListening(true);
    rec.start();
  }

  const coreState: CoreState = busy
    ? "THINKING"
    : listening
      ? "LISTENING"
      : lastResult
        ? lastResult.status === "COMPLETED"
          ? "COMPLETED"
          : lastResult.status === "FAILED"
            ? "ERROR"
            : lastResult.status === "WAITING_FOR_APPROVAL"
              ? "PLANNING"
              : "EXECUTING"
        : "IDLE";

  return (
    <div>
      <PageTitle title="AI Workspace" sub="Talk to the Master Agent — English and Roman Urdu both work. The core mirrors the real state of your last command." />
      {error ? <div className="mb-3"><ErrorBox message={error} /></div> : null}
      <div className="grid gap-4 lg:grid-cols-[240px_1fr_300px]">
        <Card className="max-h-[70vh] overflow-y-auto">
          <button onClick={newConversation} className={`${btnCls} mb-3 w-full`}>
            + New conversation
          </button>
          {conversations.length === 0 ? (
            <p className="text-xs text-zinc-500">No conversations yet.</p>
          ) : (
            <ul className="space-y-1">
              {conversations.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => selectConversation(c.id)}
                    className={`w-full rounded-xl px-2.5 py-2 text-left text-sm transition ${c.id === activeId ? "border border-cyan-300/25 bg-cyan-400/10 text-cyan-50" : "border border-transparent text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-100"}`}
                  >
                    <span className="block truncate">{c.title || "Untitled"}</span>
                    <span className="block text-[11px] text-zinc-500">{fmtDate(c.updated_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="flex max-h-[70vh] flex-col">
          <div className="mb-3 flex items-center gap-3 border-b border-white/5 pb-3">
            <AICore state={coreState} size={52} showLabel={false} />
            <div>
              <div className="font-display text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-200">Master Agent</div>
              <div className="text-xs text-zinc-500">
                Core state: <span className="text-cyan-200">{coreState}</span> — driven by the live API response, never simulated.
              </div>
            </div>
          </div>
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
            {messages.length === 0 && !lastResult ? (
              <Empty message="No messages yet. Try: “Meri pending tasks list karo” or “Generate a summary report”." />
            ) : (
              messages.map((m) => (
                <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${m.role === "user" ? "border border-cyan-300/30 bg-cyan-400/15 text-cyan-50" : "border border-white/8 bg-white/[0.05] text-zinc-100"}`}>
                    {m.role !== "user" && m.agent_key ? (
                      <div className="mb-1 text-[11px] uppercase tracking-wide opacity-60">agent: {m.agent_key}</div>
                    ) : null}
                    {m.content}
                  </div>
                </div>
              ))
            )}
            {lastResult ? (
              <div className="rounded-2xl border border-cyan-200/10 bg-black/25 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-zinc-400">Last command:</span>
                  <Badge value={lastResult.status} />
                  <span className="text-zinc-400">agent: <span className="text-zinc-200">{lastResult.agent}</span></span>
                  <span className="text-zinc-500">task {lastResult.task_id.slice(0, 8)}…</span>
                  {lastResult.approval_id ? <span className="text-amber-300">waiting for approval →</span> : null}
                </div>
              </div>
            ) : null}
            <div ref={bottomRef} />
          </div>
          <form onSubmit={send} className="mt-3 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Command likhein… e.g. Kharcha 2500 petrol / Research electric bikes"
              className={`${inputCls} min-w-0 flex-1`}
            />
            <button type="button" onClick={voiceInput} title="Voice input" className={btnGhostCls}>
              {listening ? "●" : "🎤"}
            </button>
            <button disabled={busy} className={btnCls}>
              {busy ? "Working…" : "Send"}
            </button>
          </form>
        </Card>

        <Card className="max-h-[70vh] overflow-y-auto">
          <h2 className="mb-3 font-display text-xs font-semibold uppercase tracking-[0.2em] text-zinc-200">Pending approvals</h2>
          {approvals.length === 0 ? (
            <p className="text-xs text-zinc-500">Nothing waiting for approval.</p>
          ) : (
            <ul className="space-y-3">
              {approvals.map((a) => (
                <li key={a.id} className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm">
                  <div className="font-medium text-zinc-100">{a.action}</div>
                  <p className="mt-1 whitespace-pre-wrap text-zinc-400">{a.summary}</p>
                  <div className="mt-1 text-[11px] text-zinc-500">{fmtDate(a.created_at)}</div>
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => decide(a.id, "approved")} className="rounded-lg bg-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-200 hover:bg-emerald-500/30">
                      Approve
                    </button>
                    <button onClick={() => decide(a.id, "rejected")} className="rounded-lg bg-red-500/20 px-3 py-1.5 text-xs font-medium text-red-200 hover:bg-red-500/30">
                      Reject
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
