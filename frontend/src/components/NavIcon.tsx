/**
 * Ícones da navegação, desenhados aqui em vez de vir de biblioteca.
 *
 * São onze ícones. Uma biblioteca traria algumas centenas junto, e o projeto já
 * desenha os gráficos em SVG à mão — manter o mesmo traço custa menos que
 * alinhar um pacote externo ao resto.
 *
 * O ícone não substitui o rótulo: ele acelera quem já sabe onde vai. Por isso
 * todos são `aria-hidden` e o texto ao lado continua sendo o nome acessível.
 */
const TRACOS: Record<string, string> = {
  // Painel: quatro blocos de um dashboard.
  painel: "M4 4h6v6H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 14h6v6H4z",
  // Pipeline: pulso de atividade.
  pipeline: "M3 12h4l3-8 4 16 3-8h4",
  // Mercado: toldo de banca.
  mercado: "M3 9h18M4 9V5h16v4M5 9v11h14V9M9 20v-6h6v6",
  // Histórico: série temporal.
  historico: "M4 4v16h16M8 15l4-5 3 3 4-6",
  // Arbitragem: duas pernas, duas direções.
  arbitragem: "M7 8h13l-3-3M17 16H4l3 3",
  // Crafting: martelo.
  crafting: "M14 4l6 6-3 3-6-6zM11 9l-7 7 3 3 7-7",
  // Refino: chama da fundição.
  refino: "M12 3c3 4 5 6 5 9a5 5 0 01-10 0c0-2 1-3 2-4 0 2 1 3 2 3 1 0 1-4 1-8z",
  // Focus: mira, porque é o recurso escasso que se aponta.
  focus: "M12 3v3M12 18v3M3 12h3M18 12h3M12 8a4 4 0 100 8 4 4 0 000-8z",
  // Gold: moedas empilhadas.
  gold: "M5 7c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3zM5 7v5c0 1.7 3.1 3 7 3s7-1.3 7-3V7M5 12v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5",
  // Transporte: carroça.
  transporte: "M3 6h11v10H3zM14 10h4l3 3v3h-7M7 19a2 2 0 100-4 2 2 0 000 4zM18 19a2 2 0 100-4 2 2 0 000 4z",
  // Watchlist: olho que vigia.
  watchlist: "M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6zM12 15a3 3 0 100-6 3 3 0 000 6z",
};

export type NavIconName = keyof typeof TRACOS;

export function NavIcon({ name }: { name: string }) {
  const traco = TRACOS[name];
  if (!traco) return null;

  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-[15px] shrink-0"
    >
      <path d={traco} />
    </svg>
  );
}
