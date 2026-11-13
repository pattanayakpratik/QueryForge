import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QueryForge — Autonomous Text-to-SQL & AI Analytics Studio",
  description:
    "Self-Healing Text-to-SQL microservice with SQLGlot AST Firewall, Schema Vector RAG, and Recharts auto-visualization.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased min-h-screen bg-[#090d16] text-slate-100 selection:bg-indigo-500/30 selection:text-indigo-200">
        {children}
      </body>
    </html>
  );
}
