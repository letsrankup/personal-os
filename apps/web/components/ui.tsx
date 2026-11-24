"use client";

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`glass rounded-2xl p-4 ${className}`}>{children}</div>;
}

export function Stat({
  label,
  value,
  accent = "text-cyan-100",
  hint,
}: {
  label: string;
  value: React.ReactNode;
  accent?: string;
  hint?: string;
}) {
  return (
    <Card className="relative overflow-hidden">
      <div className="pointer-events-none absolute -right-6 -top-6 h-16 w-16 rounded-full bg-cyan-400/10 blur-xl" />
      <div className="font-display text-[10px] uppercase tracking-[0.22em] text-cyan-200/60">{label}</div>
      <div className={`mt-1.5 text-3xl font-semibold ${accent}`}>{value}</div>
      {hint ? <div className="mt-1 text-xs text-zinc-400">{hint}</div> : null}
    </Card>
  );
}

const STATUS_STYLES: Record<string, string> = {
  COMPLETED: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
  RUNNING: "bg-sky-500/15 text-sky-300 border-sky-400/30",
  FAILED: "bg-red-500/15 text-red-300 border-red-400/30",
  PENDING: "bg-zinc-500/15 text-zinc-300 border-zinc-400/30",
  PLANNING: "bg-violet-500/15 text-violet-300 border-violet-400/30",
  WAITING_FOR_APPROVAL: "bg-amber-500/15 text-amber-300 border-amber-400/30",
  CANCELLED: "bg-zinc-600/20 text-zinc-400 border-zinc-500/40",
  active: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
  connected: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
  not_connected: "bg-zinc-500/15 text-zinc-300 border-zinc-400/30",
  awaiting_oauth: "bg-amber-500/15 text-amber-300 border-amber-400/30",
  error: "bg-red-500/15 text-red-300 border-red-400/30",
  pending: "bg-amber-500/15 text-amber-300 border-amber-400/30",
  approved: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
  rejected: "bg-red-500/15 text-red-300 border-red-400/30",
};

export function Badge({ value }: { value: string }) {
  const cls = STATUS_STYLES[value] ?? "bg-zinc-500/15 text-zinc-300 border-zinc-400/30";
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}>{value}</span>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-sm text-cyan-100/60">
      <span className="relative flex h-10 w-10">
        <span className="absolute inline-flex h-full w-full animate-spin rounded-full border-2 border-cyan-400/20 border-t-cyan-300" />
        <span className="m-auto h-2.5 w-2.5 rounded-full bg-cyan-300 shadow-[0_0_14px_rgba(34,211,238,0.9)]" />
      </span>
      {label}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{message}</div>
  );
}

export function Empty({ message }: { message: string }) {
  return (
    <div className="glass rounded-2xl border-dashed p-8 text-center text-sm text-zinc-500">{message}</div>
  );
}

export function PageTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-6">
      <h1 className="font-display text-xl font-bold uppercase tracking-[0.14em] text-zinc-50 md:text-2xl">
        <span className="text-gradient">{title}</span>
      </h1>
      {sub ? <p className="mt-1 text-sm text-zinc-400">{sub}</p> : null}
    </div>
  );
}

/* ---------- Shared futuristic controls ---------- */

export const inputCls =
  "w-full rounded-xl border border-cyan-200/15 bg-white/[0.04] px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 outline-none backdrop-blur transition focus:border-cyan-300/50 focus:bg-white/[0.06] focus:shadow-[0_0_0_3px_rgba(34,211,238,0.12)]";

export const btnCls =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-cyan-300/40 bg-cyan-400/15 px-4 py-2.5 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/25 hover:shadow-[0_0_24px_-6px_rgba(34,211,238,0.7)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50";

export const btnGhostCls =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-cyan-300/30 hover:text-cyan-100 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50";

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-display text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-200/50">
      {children}
    </div>
  );
}
