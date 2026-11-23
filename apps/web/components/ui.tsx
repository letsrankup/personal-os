"use client";

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 ${className}`}>{children}</div>
  );
}

export function Stat({ label, value, accent = "text-zinc-100" }: { label: string; value: React.ReactNode; accent?: string }) {
  return (
    <Card>
      <div className="text-xs uppercase tracking-wide text-zinc-400">{label}</div>
      <div className={`mt-1 text-3xl font-semibold ${accent}`}>{value}</div>
    </Card>
  );
}

const STATUS_STYLES: Record<string, string> = {
  COMPLETED: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  RUNNING: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  FAILED: "bg-red-500/15 text-red-300 border-red-500/30",
  PENDING: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
  PLANNING: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  WAITING_FOR_APPROVAL: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  CANCELLED: "bg-zinc-600/20 text-zinc-400 border-zinc-600/40",
  active: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  connected: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  not_connected: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
  awaiting_oauth: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  error: "bg-red-500/15 text-red-300 border-red-500/30",
  pending: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  approved: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  rejected: "bg-red-500/15 text-red-300 border-red-500/30",
};

export function Badge({ value }: { value: string }) {
  const cls = STATUS_STYLES[value] ?? "bg-zinc-500/15 text-zinc-300 border-zinc-500/30";
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}>{value}</span>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="py-10 text-center text-sm text-zinc-400">{label}</div>;
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{message}</div>
  );
}

export function Empty({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">{message}</div>
  );
}

export function PageTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-xl font-semibold text-zinc-50">{title}</h1>
      {sub ? <p className="mt-0.5 text-sm text-zinc-400">{sub}</p> : null}
    </div>
  );
}
