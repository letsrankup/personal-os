"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import type { FinanceEntry } from "@/lib/types";
import { Card, Empty, ErrorBox, Loading, PageTitle, SectionLabel, Stat, fmtDate } from "@/components/ui";
import { usePolling } from "@/lib/usePolling";

const PIE_COLORS = ["#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#f472b6", "#fb923c", "#38bdf8", "#e879f9"];

function money(n: number, currency: string): string {
  return `${currency} ${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function FinancePage() {
  const [entries, setEntries] = useState<FinanceEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api<FinanceEntry[]>("/finance?limit=300")
      .then((rows) => {
        setEntries(rows);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  usePolling(refresh, 30000);

  const stats = useMemo(() => {
    const rows = entries ?? [];
    const currency = rows[0]?.currency ?? "PKR";
    let income = 0;
    let expense = 0;
    const now = new Date();
    let monthIncome = 0;
    let monthExpense = 0;
    const byCategory = new Map<string, number>();
    const days: { date: string; label: string; income: number; expense: number }[] = [];
    const dayMap = new Map<string, { income: number; expense: number }>();
    for (let i = 13; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(now.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      dayMap.set(key, { income: 0, expense: 0 });
      days.push({ date: key, label: d.toLocaleDateString(undefined, { day: "numeric", month: "short" }), income: 0, expense: 0 });
    }
    for (const r of rows) {
      const amt = Number(r.amount) || 0;
      const when = new Date(r.occurred_at);
      if (r.kind === "income") income += amt;
      else expense += amt;
      if (when.getMonth() === now.getMonth() && when.getFullYear() === now.getFullYear()) {
        if (r.kind === "income") monthIncome += amt;
        else monthExpense += amt;
      }
      if (r.kind === "expense") {
        byCategory.set(r.category || "general", (byCategory.get(r.category || "general") ?? 0) + amt);
      }
      const slot = dayMap.get(r.occurred_at.slice(0, 10));
      if (slot) {
        if (r.kind === "income") slot.income += amt;
        else slot.expense += amt;
      }
    }
    for (const d of days) {
      const slot = dayMap.get(d.date);
      if (slot) {
        d.income = slot.income;
        d.expense = slot.expense;
      }
    }
    const pie = [...byCategory.entries()]
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
    return { currency, income, expense, net: income - expense, monthNet: monthIncome - monthExpense, days, pie };
  }, [entries]);

  if (error && !entries) return <ErrorBox message={error} />;
  if (!entries) return <Loading label="Loading finance ledger…" />;

  return (
    <div className="space-y-4">
      <PageTitle
        title="Finance"
        sub="Real ledger from the Finance Agent — entries are recorded only through commands, and money never moves from here."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Total income" value={money(stats.income, stats.currency)} accent="text-emerald-300" />
        <Stat label="Total expenses" value={money(stats.expense, stats.currency)} accent="text-red-300" />
        <Stat label="Net balance" value={money(stats.net, stats.currency)} accent={stats.net >= 0 ? "text-cyan-200" : "text-red-300"} />
        <Stat label="This month (net)" value={money(stats.monthNet, stats.currency)} accent={stats.monthNet >= 0 ? "text-emerald-300" : "text-amber-300"} hint={`${entries.length} entries recorded`} />
      </div>

      {entries.length === 0 ? (
        <Empty message="No finance entries yet. Try a command: “Kharcha 2500 petrol ka likho” or “Income 50000 salary ayi”." />
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-5">
            <Card className="lg:col-span-3">
              <SectionLabel>Income vs expenses — last 14 days</SectionLabel>
              <div className="mt-3 h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.days} margin={{ top: 5, right: 5, left: -12, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,197,255,0.12)" />
                    <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} interval={1} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: "#0a0f1e", border: "1px solid rgba(34,211,238,0.25)", borderRadius: 12, color: "#e6edf3" }}
                      cursor={{ fill: "rgba(34,211,238,0.06)" }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="income" name="Income" fill="#34d399" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="expense" name="Expenses" fill="#f87171" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card className="lg:col-span-2">
              <SectionLabel>Expenses by category</SectionLabel>
              <div className="mt-3 h-[260px]">
                {stats.pie.length === 0 ? (
                  <Empty message="No expenses recorded yet." />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={stats.pie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3} strokeWidth={0}>
                        {stats.pie.map((p, i) => (
                          <Cell key={p.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: "#0a0f1e", border: "1px solid rgba(34,211,238,0.25)", borderRadius: 12, color: "#e6edf3" }}
                        formatter={(value) => money(Number(value ?? 0), stats.currency)}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>
          </div>

          <Card>
            <SectionLabel>Latest entries</SectionLabel>
            <ul className="mt-3 space-y-2 text-sm">
              {entries.slice(0, 25).map((r) => (
                <li key={r.id} className="flex items-baseline justify-between gap-3 border-b border-white/5 pb-2 last:border-0">
                  <span className="min-w-0">
                    <span className={r.kind === "income" ? "text-emerald-300" : "text-red-300"}>{r.kind === "income" ? "▲" : "▼"}</span>{" "}
                    <span className="text-zinc-200">{r.note || r.category}</span>{" "}
                    <span className="text-xs text-zinc-500">[{r.category}]</span>
                  </span>
                  <span className="flex shrink-0 items-baseline gap-3">
                    <span className={`font-medium ${r.kind === "income" ? "text-emerald-300" : "text-red-300"}`}>
                      {r.kind === "income" ? "+" : "−"} {money(r.amount, r.currency)}
                    </span>
                    <span className="hidden text-xs text-zinc-500 sm:inline">{fmtDate(r.occurred_at)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}

      <Card>
        <SectionLabel>Add an entry</SectionLabel>
        <p className="mt-2 text-sm leading-relaxed text-zinc-400">
          Entries are recorded by the Finance Agent from natural commands — for example{" "}
          <span className="text-zinc-200">“Kharcha 1200 khana”</span>,{" "}
          <span className="text-zinc-200">“Income 75000 client payment”</span>, or ask{" "}
          <span className="text-zinc-200">“Is month ka hisab do”</span> for a summary.{" "}
          <Link href="/command" className="font-medium text-cyan-300 hover:underline">
            Open AI Workspace →
          </Link>
        </p>
      </Card>
    </div>
  );
}
