import type { Opportunity } from "@/lib/api";
import { formatDataAge, formatSilver } from "@/lib/format";

import { CityChip } from "./CityChip";
import { ItemIcon } from "./ItemIcon";

const BANDA: Record<string, string> = {
  excelente: "text-up border-up/50",
  muito_boa: "text-up border-up/30",
  boa: "text-body border-line-strong",
  moderada: "text-warn border-warn/40",
  ruim: "text-down border-down/40",
  desconhecida: "text-muted border-line",
};

const TOM_IDADE = (segundos: number) =>
  segundos <= 900 ? "text-up" : segundos <= 21600 ? "text-warn" : "text-down";

export function OpportunityRow({ opportunity }: { opportunity: Opportunity }) {
  const { economics: eco, score } = opportunity;

  return (
    <article className="flex flex-wrap items-stretch gap-4 border-line/60 border-b py-3 last:border-0">
      {/* item */}
      <div className="flex min-w-56 flex-1 gap-3">
        <ItemIcon
          url={opportunity.icon_url}
          alt={opportunity.item_name ?? opportunity.item}
          tier={opportunity.tier}
        />
        <div className="min-w-0">
          <div className="mb-1 flex items-center gap-1.5">
            <span className="figure rounded-sm border border-line-strong px-1.5 py-0.5 text-[11px]">
              T{opportunity.tier ?? "?"}
              {opportunity.enchantment ? `.${opportunity.enchantment}` : ""}
            </span>
            <span className="figure rounded-sm bg-ink-raised px-1.5 py-0.5 text-[11px] text-muted">
              Q{opportunity.quality}
            </span>
          </div>
          <p className="truncate text-body text-sm leading-tight">
            {opportunity.item_name ?? opportunity.item}
          </p>
          <p className="figure truncate text-muted text-[11px]">{opportunity.item}</p>
        </div>
      </div>

      {/* rota */}
      <div className="min-w-52 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Rota</p>
        <div className="mt-1 flex flex-col gap-1">
          <span className="flex items-center justify-between gap-2">
            <CityChip city={opportunity.origin} />
            <span className="figure text-body text-sm">
              {formatSilver(opportunity.buy_price)}
            </span>
          </span>
          <span className="flex items-center justify-between gap-2">
            <CityChip city={opportunity.destination} />
            <span className="figure text-body text-sm">
              {formatSilver(opportunity.sell_price)}
            </span>
          </span>
        </div>
        <p className="mt-1 flex justify-between text-[11px]">
          <span className="text-muted" title="diferença de preço antes de qualquer taxa">
            spread bruto
          </span>
          <span className="figure text-muted">{opportunity.spread_pct.toFixed(1)}%</span>
        </p>
      </div>

      {/* economia */}
      <div className="min-w-48 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Lucro líquido</p>
        <p className="mb-1.5 text-muted text-[11px]">
          {formatSilver(eco.quantity)} un · depois de taxas
        </p>

        {!eco.known ? (
          <div className="rounded-sm border border-line-strong border-dashed px-2 py-1.5">
            <p className="figure text-muted text-xs">UNKNOWN</p>
            <p className="mt-0.5 text-[11px] text-muted leading-snug">{eco.reason}</p>
          </div>
        ) : (
          <>
            <p
              className={`figure text-base ${
                (eco.net_profit ?? 0) > 0 ? "text-up" : "text-down"
              }`}
            >
              {(eco.net_profit ?? 0) > 0 ? "+" : ""}
              {formatSilver(eco.net_profit)}
            </p>
            <p className="flex justify-between text-[11px]">
              <span className="text-muted">margem</span>
              <span className="figure text-body">{eco.margin_pct?.toFixed(1)}%</span>
            </p>
            <p className="flex justify-between text-[11px]">
              <span className="text-muted">ROI</span>
              <span className="figure text-body">{eco.roi_pct?.toFixed(1)}%</span>
            </p>
            <p className="flex justify-between text-[11px]">
              <span className="text-muted">taxas</span>
              <span className="figure text-muted">{formatSilver(eco.fees)}</span>
            </p>
          </>
        )}
      </div>

      {/* confiança */}
      <div className="min-w-40 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Score</p>
        <p className="mb-1.5 text-muted text-[11px]">qualidade da oportunidade</p>

        <span
          className={`inline-flex items-baseline gap-2 rounded-sm border px-2 py-1 ${
            BANDA[score.band] ?? BANDA.desconhecida
          }`}
        >
          <span className="figure text-base">{score.value ?? "—"}</span>
          <span className="text-[11px]">{score.band.replace("_", " ")}</span>
        </span>

        {score.value === null && score.missing.length > 0 && (
          <p className="mt-1 text-[11px] text-muted leading-snug">
            sem dado para: {score.missing.join(", ")}
          </p>
        )}

        <p className="mt-1.5 flex justify-between text-[11px]">
          <span className="text-muted">preço mais velho</span>
          <span className={`figure ${TOM_IDADE(opportunity.worst_age_seconds)}`}>
            {formatDataAge(opportunity.worst_age_seconds)}
          </span>
        </p>
        <p className="flex justify-between text-[11px]">
          <span className="text-muted">giro no destino</span>
          <span className="figure text-muted">
            {opportunity.liquidity_units_per_day === null
              ? "desconhecido"
              : `${formatSilver(opportunity.liquidity_units_per_day)}/dia`}
          </span>
        </p>
      </div>
    </article>
  );
}
