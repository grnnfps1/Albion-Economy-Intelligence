import type { Metadata } from "next";

import { Sidebar } from "@/components/Sidebar";
import { getSession } from "@/lib/auth";

import "./globals.css";

export const metadata: Metadata = {
  title: "Albion Economy Intelligence",
  description:
    "Inteligência econômica para Albion Online: mercado, arbitragem, crafting, refinamento e Focus.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  return (
    <html lang="pt-BR">
      <body className="min-h-dvh">
        <div className="flex min-h-dvh flex-col md:flex-row">
          <Sidebar session={session} />
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
