import Link from "next/link";

/**
 * Navegação do produto inteiro, com o que ainda não existe marcado pela fase em
 * que entra. Esconder as seções futuras daria a impressão de um produto menor;
 * mostrá-las como links falsos seria mentira. Rótulo de fase resolve os dois.
 */
const SECTIONS: { label: string; href: string; phase: number | null }[] = [
  { label: "Painel", href: "/", phase: null },
  { label: "Mercado", href: "/market", phase: null },
  { label: "Histórico", href: "/market/history", phase: null },
  { label: "Arbitragem", href: "/arbitrage", phase: null },
  { label: "Crafting", href: "/crafting", phase: null },
  { label: "Refinamento", href: "/refining", phase: null },
  { label: "Focus", href: "/focus", phase: null },
  { label: "Gold", href: "/gold", phase: null },
  { label: "Transporte", href: "/transport", phase: 6 },
  { label: "Watchlist", href: "/watchlist", phase: null },
];

export function Sidebar() {
  return (
    <nav
      aria-label="Seções"
      className="flex w-full shrink-0 flex-col gap-1 border-line border-b bg-ink-sunken p-4 md:h-dvh md:w-56 md:border-r md:border-b-0"
    >
      <div className="mb-6 hidden md:block">
        <p className="font-semibold text-[15px] text-body leading-tight">
          Albion Economy
          <br />
          Intelligence
        </p>
        <p className="mt-1 text-muted text-xs">Fase 9 — focus</p>
      </div>

      <ul className="flex flex-row gap-1 overflow-x-auto md:flex-col md:overflow-visible">
        {SECTIONS.map((section) => {
          const available = section.phase === null && section.href !== "/watchlist";
          return (
            <li key={section.href} className="shrink-0">
              {available ? (
                <Link
                  href={section.href}
                  className="block rounded-sm bg-ink-raised px-3 py-1.5 text-body text-sm"
                >
                  {section.label}
                </Link>
              ) : (
                <span
                  className="flex items-center justify-between gap-3 rounded-sm px-3 py-1.5 text-muted text-sm"
                  title={
                    section.phase
                      ? `Entra na fase ${section.phase}`
                      : "Ainda não planejado em detalhe"
                  }
                >
                  {section.label}
                  <span className="figure text-[10px] text-line-strong">
                    {section.phase ? `F${section.phase}` : "—"}
                  </span>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
