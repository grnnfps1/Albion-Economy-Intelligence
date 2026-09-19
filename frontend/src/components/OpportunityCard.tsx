import Link from "next/link";

import type { DashboardCard } from "@/lib/api";
import { formatDataAge, formatSilver } from "@/lib/format";

import { ItemIcon } from "@/components/ui/ItemIcon";

const TITULO: Record<string, string> = {
  ARBITRAGEM: "Melhor arbitragem",
  CRAFTING: "Melhor crafting",
  REFINO: "Melhor refino",
  FOCUS: "Melhor uso do focus",
};

const TOM: Record<string, string> = {
  ATUALIZADO: "text-up",
  DESATUALIZADO: "text-warn",
  ANTIGO: "text-down",
  DESCONHECIDO: "text-muted",
};

/**
 * Card com o contexto que torna o número confiável.
 *
 * Um dashboard que mostra só o maior número de cada categoria seria vitrine: o
 * usuário decide sobre uma cotação de ontem sem saber. Idade, confiança e giro
 * vêm junto, sempre.
 */
export function OpportunityCard({
  card,
  destaque = false,
}: {
  card: DashboardCard;
  destaque?: boolean;
}) {
  if (!card.available) {
    return (
      <Link
        href={card.href}
        className="flex min-h-32 flex-col justify-between rounded-sm border border-line border-dashed p-3 transition-colors duration-150 hover:border-line-strong hover:bg-raised/30"
      >
        <p className="lbl">{TITULO[card.kind] ?? card.kind}</p>
        <p className="text-muted text-sm leading-snug">{card.reason}</p>
        <p className="text-muted text-note">abrir a tela →</p>
      </Link>
    );
  }

  return (
    <Link
      href={card.href}
      className={`flex min-h-32 flex-col justify-between rounded-sm border p-3 transition-colors duration-150 ${
        destaque
          ? // O melhor card da tela ganha moldura dourada. É o único lugar do
            // painel em que ouro aparece perto de número, e por isso ele é um
            // só: dois destaques não destacam nada.
            "border-accent/40 bg-[linear-gradient(160deg,rgba(200,162,83,0.10),transparent_55%)] hover:border-accent/70"
          : "border-line bg-raised/40 hover:border-line-strong"
      }`}
    >
      <p className={`lbl ${destaque ? "text-accent" : ""}`}>{TITULO[card.kind] ?? card.kind}</p>

      <div className="flex items-center gap-2.5">
        <ItemIcon url={card.icon_url} alt={card.item_name ?? ""} tier={card.tier} size={36} />
        <div className="min-w-0">
          <p className="truncate text-body text-sm leading-tight">
            {card.item_name ?? card.item}
          </p>
          <p className="truncate text-muted text-note">{card.detail}</p>
        </div>
      </div>

      <div>
        <p className="figure text-up text-lg leading-tight">
          {formatSilver(card.headline)}
        </p>
        <p className="text-muted text-note">{card.headline_label}</p>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-note">
        {card.age_seconds !== null && (
          <span className={`figure ${TOM[card.freshness]}`}>
            {formatDataAge(card.age_seconds)}
          </span>
        )}
        {card.score !== null && (
          <span className="figure text-muted">score {card.score}</span>
        )}
        {card.confidence !== null && (
          <span className="figure text-muted" title="fração dos sinais disponíveis">
            conf {card.confidence}
          </span>
        )}
        {card.liquidity_units_per_day !== null && (
          <span className="figure text-muted">
            {formatSilver(card.liquidity_units_per_day)}/dia
          </span>
        )}
      </div>
    </Link>
  );
}
