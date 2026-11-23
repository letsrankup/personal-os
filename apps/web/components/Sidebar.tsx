"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, setToken } from "@/lib/api";
import type { User } from "@/lib/types";

const LINKS: { href: string; label: string }[] = [
  { href: "/", label: "Overview" },
  { href: "/command", label: "Command Center" },
  { href: "/agents", label: "Agents" },
  { href: "/tasks", label: "Tasks" },
  { href: "/projects", label: "Projects" },
  { href: "/clients", label: "Clients" },
  { href: "/research", label: "Research" },
  { href: "/files", label: "Files" },
  { href: "/reports", label: "Reports" },
  { href: "/memory", label: "Memory" },
  { href: "/integrations", label: "Integrations" },
  { href: "/security", label: "Security & Permissions" },
  { href: "/settings", label: "Settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    api<User>("/auth/me").then(setUser).catch(() => undefined);
  }, []);

  function logout() {
    setToken(null);
    router.push("/login");
  }

  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-zinc-800 bg-zinc-950 md:h-screen md:w-60 md:border-b-0 md:border-r">
      <div className="px-4 pb-2 pt-4">
        <div className="text-base font-bold tracking-tight text-zinc-50">PERSONAL OS</div>
        <div className="text-[11px] uppercase tracking-widest text-zinc-500">AI Command Center</div>
        {user ? <div className="mt-2 truncate text-xs text-zinc-400">{user.email}</div> : null}
      </div>
      <nav className="flex flex-1 flex-row flex-wrap gap-1 overflow-y-auto p-2 md:flex-col md:flex-nowrap">
        {LINKS.map((l) => {
          const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-lg px-3 py-2 text-sm ${
                active ? "bg-zinc-800 text-zinc-50" : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-3">
        <button
          onClick={logout}
          className="w-full rounded-lg border border-zinc-800 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
        >
          Log out
        </button>
      </div>
    </aside>
  );
}
