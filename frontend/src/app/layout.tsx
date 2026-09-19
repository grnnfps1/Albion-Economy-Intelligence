import type { Metadata } from "next";
import { Cinzel, Inter } from "next/font/google";

import { Sidebar } from "@/components/Sidebar";
import { getSession } from "@/lib/auth";

import "./globals.css";

/**
 * Duas fontes, com papéis separados.
 *
 * Cinzel é serifada de inscrição e carrega a pegada do jogo — mas só em marca e
 * título. Numa linha de tabela com quarenta itens ela atrapalha: serifa em
 * corpo 11 vira ruído.
 *
 * Inter faz o corpo e os dados. `display: swap` porque a tela é útil antes da
 * fonte chegar; bloquear o texto por causa de tipografia seria trocar o
 * conteúdo pelo enfeite.
 */
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const cinzel = Cinzel({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-cinzel",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Albion Economy Intelligence",
  description:
    "Inteligência econômica para Albion Online: mercado, arbitragem, crafting, refinamento e Focus.",
};

/**
 * Aviso de que a sessão foi dispensada.
 *
 * Um app que **parece** logado e não está é o pior resultado possível de um
 * desvio de autenticação: alguém demonstra a tela, conclui que o portão
 * funciona, e ele não foi exercitado nenhuma vez. A tira existe para esse
 * engano não caber.
 *
 * Ela desaparece de produção pelo mesmo mecanismo do middleware — a condição
 * vira literal no build e o bloco é eliminado. Não é "escondida em produção":
 * não está lá.
 */
function AvisoDeDesvio() {
  if (process.env.NODE_ENV !== "development" || process.env.DEV_AUTH_BYPASS !== "1") {
    return null;
  }
  return (
    <div className="shrink-0 bg-warn/15 px-4 py-1 text-center font-semibold text-[11px] text-warn">
      DEV_AUTH_BYPASS ligado — a sessão foi dispensada e ninguém está autenticado. O portão
      não está sendo testado.
    </div>
  );
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  return (
    <html lang="pt-BR" className={`${inter.variable} ${cinzel.variable}`}>
      <body className="min-h-dvh">
        <AvisoDeDesvio />
        <div className="flex min-h-dvh flex-col md:flex-row">
          <Sidebar session={session} />
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
