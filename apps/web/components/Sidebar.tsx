"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, setToken } from "@/lib/api";
import type { User } from "@/lib/types";

function Icon({ d, className = "h-[18px] w-[18px]" }: { d: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

const PATHS = {
  overview: "M3 12l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  brain: "M12 3a4.5 4.5 0 0 1 4.5 4.5c2 .6 3.5 2.3 3.5 4.5s-1.5 3.9-3.5 4.5A4.5 4.5 0 0 1 12 21a4.5 4.5 0 0 1-4.5-4.5C5.5 15.9 4 14.2 4 12s1.5-3.9 3.5-4.5A4.5 4.5 0 0 1 12 3zM12 3v18",
  command: "M4 17l6-5-6-5M12 19h8M4 4h16v16H4z",
  agents: "M12 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM5 21c0-3.3 3.1-5 7-5s7 1.7 7 5M18.5 8.5a2.5 2.5 0 1 0-1.6-4.4M21 21c0-2.4-1-3.9-2.7-4.6",
  tasks: "M9 6h11M9 12h11M9 18h11M4 5l1 1 2-2M4 11l1 1 2-2M4 17l1 1 2-2",
  projects: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  clients: "M4 7h16M4 7v13h16V7M4 7l2-3h12l2 3M9 20v-6h6v6",
  research: "M11 5a6 6 0 1 0 0 12 6 6 0 0 0 0-12zM20 20l-3.8-3.8",
  files: "M6 2h8l4 4v16H6zM14 2v4h4M9 12h6M9 16h6",
  reports: "M4 20V10M10 20V4M16 20v-8M21 20H3",
  memory: "M5 4h14v16H5zM9 4v16M9 8h6M9 12h6",
  finance: "M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM16 12.5h.01M3 10h18",
  integrations: "M9 7V4M15 7V4M7 7h10v4a5 5 0 0 1-10 0zM12 16v5",
  security: "M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6zM9.5 12l2 2 3.5-4",
  settings: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1",
};

const LINKS: { href: string; label: string; icon: string }[] = [
  { href: "/", label: "Command Center", icon: PATHS.overview },
  { href: "/brain", label: "AI Brain", icon: PATHS.brain },
  { href: "/command", label: "AI Workspace", icon: PATHS.command },
  { href: "/agents", label: "Agent Network", icon: PATHS.agents },
  { href: "/tasks", label: "Tasks", icon: PATHS.tasks },
  { href: "/projects", label: "Projects", icon: PATHS.projects },
  { href: "/clients", label: "Clients / CRM", icon: PATHS.clients },
  { href: "/research", label: "Research", icon: PATHS.research },
  { href: "/files", label: "Files", icon: PATHS.files },
  { href: "/reports", label: "Reports", icon: PATHS.reports },
  { href: "/memory", label: "Memory", icon: PATHS.memory },
  { href: "/finance", label: "Finance", icon: PATHS.finance },
  { href: "/integrations", label: "Integrations", icon: PATHS.integrations },
  { href: "/security", label: "Security", icon: PATHS.security },
  { href: "/settings", label: "Settings", icon: PATHS.settings },
];

export function CoreMark({ size = 38 }: { size?: number }) {
  return (
    <span className="relative inline-flex shrink-0" style={{ width: size, height: size }} aria-hidden="true">
      <span className="absolute inset-0 animate-spin-slow rounded-full border border-dashed border-cyan-300/50" />
      <span className="absolute inset-[5px] animate-spin-rev rounded-full border border-violet-400/40 border-t-transparent" />
      <span className="absolute inset-0 m-auto h-[38%] w-[38%] animate-core-pulse rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(34,211,238,0.95)]" />
    </span>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api<User>("/auth/me").then(setUser).catch(() => undefined);
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  function logout() {
    setToken(null);
    router.push("/login");
  }

  const nav = (
    <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-3">
      {LINKS.map((l) => {
        const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            className={`group flex items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium transition ${
              active
                ? "border border-cyan-300/25 bg-cyan-400/10 text-cyan-100 shadow-[0_0_18px_-6px_rgba(34,211,238,0.8)]"
                : "border border-transparent text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-100"
            }`}
          >
            <Icon d={l.icon} className={`h-[17px] w-[17px] ${active ? "text-cyan-300" : "text-zinc-500 group-hover:text-cyan-200"}`} />
            {l.label}
            {active ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_8px_rgba(34,211,238,1)]" /> : null}
          </Link>
        );
      })}
    </nav>
  );

  const brand = (
    <div className="flex items-center gap-3 px-4 pb-3 pt-4">
      <CoreMark />
      <div className="min-w-0">
        <div className="font-display text-[15px] font-bold tracking-[0.18em] text-zinc-50">
          PERSONAL <span className="text-cyan-300 text-glow">OS</span>
        </div>
        <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500">AI Command Center</div>
        {user ? <div className="mt-1 truncate text-[11px] text-zinc-500">{user.email}</div> : null}
      </div>
    </div>
  );

  const logoutBtn = (
    <div className="p-3">
      <button
        onClick={logout}
        className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-zinc-300 transition hover:border-red-300/30 hover:text-red-200"
      >
        Log out
      </button>
    </div>
  );

  return (
    <>
      {/* Mobile top bar */}
      <header className="sticky top-0 z-40 border-b border-cyan-200/10 bg-[#04060d]/85 backdrop-blur-xl md:hidden">
        <div className="flex items-center gap-3 px-4 py-2.5">
          <CoreMark size={30} />
          <div className="font-display text-sm font-bold tracking-[0.18em] text-zinc-50">
            PERSONAL <span className="text-cyan-300">OS</span>
          </div>
          <button
            onClick={() => setOpen((v) => !v)}
            className="ml-auto rounded-lg border border-white/10 px-3 py-1.5 text-sm text-zinc-200"
            aria-label="Toggle menu"
          >
            {open ? "✕" : "☰"}
          </button>
        </div>
        {open ? (
          <div className="max-h-[70vh] overflow-y-auto border-t border-white/5">
            {nav}
            {logoutBtn}
          </div>
        ) : null}
      </header>

      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-cyan-200/10 bg-white/[0.02] backdrop-blur-xl md:flex">
        {brand}
        {nav}
        {logoutBtn}
      </aside>
    </>
  );
}
