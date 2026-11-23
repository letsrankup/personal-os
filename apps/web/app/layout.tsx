import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PERSONAL OS — AI Command Center",
  description: "Autonomous personal AI employee & command center",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0b0f14] text-zinc-100 antialiased">{children}</body>
    </html>
  );
}
