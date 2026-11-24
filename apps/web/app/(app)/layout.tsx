"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import PageTransition from "@/components/PageTransition";
import { api, getToken } from "@/lib/api";
import type { User } from "@/lib/types";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api<User>("/auth/me")
      .then(() => setReady(true))
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-sm text-cyan-100/60">
        <span className="relative flex h-12 w-12">
          <span className="absolute inline-flex h-full w-full animate-spin rounded-full border-2 border-cyan-400/20 border-t-cyan-300" />
          <span className="m-auto h-3 w-3 rounded-full bg-cyan-300 shadow-[0_0_16px_rgba(34,211,238,0.9)]" />
        </span>
        Initializing Personal OS…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar />
      <main className="mx-auto w-full min-w-0 max-w-[1400px] flex-1 p-4 md:p-7">
        <PageTransition>{children}</PageTransition>
      </main>
    </div>
  );
}
