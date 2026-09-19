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

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  return (
    <html lang="pt-BR" className={`${inter.variable} ${cinzel.variable}`}>
      <body className="min-h-dvh">
        {/* Em telas largas o app ocupa exatamente a janela e **nada** rola
            aqui: quem rola é a tabela, lá dentro. Era isto que faltava para
            haver uma barra só — com a página rolando *e* a tabela rolando,
            apareciam duas, e a de fora movia o cabeçalho que a de dentro
            acabara de prender.

            Abaixo de `md` o comportamento antigo continua: a página rola
            inteira, porque numa tela estreita prender a tabela deixaria a
            janela de leitura menor que a própria linha. */}
        <div className="flex min-h-dvh flex-col md:h-dvh md:flex-row md:overflow-hidden">
          <Sidebar session={session} />
          <main className="flex min-w-0 flex-1 flex-col md:min-h-0">{children}</main>
        </div>
      </body>
    </html>
  );
}
