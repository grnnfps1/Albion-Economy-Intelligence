import type { CraftOpportunity } from "@/lib/api";
import { formatDataAge, formatSilver } from "@/lib/format";

import { ItemIcon } from "./ItemIcon";

const TOM_IDADE = (s: number | null) =>
  s === null ? "text-muted" : s <= 900 ? "text-up" : s <= 21600 ? "text-warn" : "text-down";

export function CraftRow({ opportunity }: { opportunity: CraftOpportunity }) {
  const eco = opportunity.economics;

  return (
    <article className="flex flex-wrap items-stretch gap-4 border-line/60 border-b py-3 last:border-0">
      {/* item final */}
      <div className="flex min-w-52 flex-1 gap-3">
        <ItemIcon
          url={opportunity.icon_url}
          alt={opportunity.item_name ?? opportunity.item}
          tier={opportunity.tier}
          size={52}
        />
        <div className="min-w-0">
          <div className="mb-1 flex flex-wrap items-center gap-1.5">
            <span className="figure rounded-sm border border-line-strong px-1.5 py-0.5 text-[11px]">
              T{opportunity.tier ?? "?"}
              {opportunity.enchantment ? `.${opportunity.enchantment}` : ""}
            </span>
            {opportunity.station_category && (
              <span className="rounded-sm bg-ink-raised px-1.5 py-0.5 text-[11px] text-muted">
                {opportunity.station_category}
              </span>
            )}
            {opportunity.recipe_variant > 0 && (
              <span
                className="rounded-sm bg-ink-raised px-1.5 py-0.5 text-[11px] text-muted"
                title="receita alternativa: o mesmo item pode ser feito de mais de um jeito"
              >
                receita {opportunity.recipe_variant + 1}
              </span>
            )}
          </div>
          <p className="truncate text-body text-sm leading-tight">
            {opportunity.item_name ?? opportunity.item}
          </p>
          <p className="figure truncate text-muted text-[11px]">{opportunity.item}</p>
        </div>
      </div>

      {/* materiais */}
      <div className="min-w-56 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Materiais</p>
        <p className="mb-1.5 text-muted text-[11px]">comprando em {opportunity.buy_location}</p>

        {opportunity.materials.map((material) => (
          <div key={material.item} className="mb-1 flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2">
              <ItemIcon
                url={material.icon_url}
                alt={material.item_name ?? material.item}
                quantity={material.quantity}
                size={28}
              />
              <span className="truncate text-muted text-xs">
                {material.item_name ?? material.item}
                {!material.is_returnable && (
                  <span className="ml-1 text-[10px]" title="não retorna no craft">
                    ·
                  </span>
                )}
              </span>
            </span>
            <span className="flex shrink-0 items-baseline gap-2">
              {material.unit_price === null ? (
                <span className="text-muted text-[11px]">sem dado</span>
              ) : (
                <>
                  <span className="figure text-body text-xs">
                    {formatSilver(material.total_price)}
                  </span>
                  <span className={`figure text-[11px] ${TOM_IDADE(material.age_seconds)}`}>
                    {formatDataAge(material.age_seconds)}
                  </span>
                </>
              )}
            </span>
          </div>
        ))}

        {eco.known && (
          <p className="mt-1.5 flex justify-between border-line border-t pt-1 text-[11px]">
            <span className="text-muted">custo líquido</span>
            <span className="figure text-body">
              {formatSilver(eco.material_cost_net)}
              <span className="ml-1 text-muted">
                (−{formatSilver(eco.returned_value)} retorno)
              </span>
            </span>
          </p>
        )}
      </div>

      {/* receita */}
      <div className="min-w-40 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Venda</p>
        <p className="mb-1.5 text-muted text-[11px]">em {opportunity.sell_location}</p>

        <p className="flex items-baseline justify-between gap-2">
          {opportunity.sell_price === null ? (
            <span className="text-muted text-xs">sem cotação</span>
          ) : (
            <>
              <span className="figure text-body text-sm">
                {formatSilver(opportunity.sell_price)}
              </span>
              <span className={`figure text-[11px] ${TOM_IDADE(opportunity.sell_age_seconds)}`}>
                {formatDataAge(opportunity.sell_age_seconds)}
              </span>
            </>
          )}
        </p>
        <p className="flex justify-between text-[11px]">
          <span className="text-muted">giro</span>
          <span className="figure text-muted">
            {opportunity.liquidity_units_per_day === null
              ? "desconhecido"
              : `${formatSilver(opportunity.liquidity_units_per_day)}/dia`}
          </span>
        </p>
        <p className="flex justify-between text-[11px]">
          <span className="text-muted">focus</span>
          <span className="figure text-body">{formatSilver(eco.focus_cost)}</span>
        </p>
      </div>

      {/* resultado */}
      <div className="min-w-44 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Prata / focus</p>
        <p className="mb-1.5 text-muted text-[11px]">focus é o recurso escasso</p>

        {!eco.known ? (
          <div className="rounded-sm border border-line-strong border-dashed px-2 py-1.5">
            <p className="figure text-muted text-xs">UNKNOWN</p>
            <p className="mt-0.5 text-[11px] text-muted leading-snug">{eco.reason}</p>
          </div>
        ) : (
          <>
            <p
              className={`figure text-lg ${
                (eco.profit_per_focus ?? 0) > 0 ? "text-up" : "text-down"
              }`}
            >
              {eco.profit_per_focus === null
                ? "—"
                : `${(eco.profit_per_focus ?? 0) > 0 ? "+" : ""}${formatSilver(eco.profit_per_focus)}`}
            </p>
            <p className="flex justify-between text-[11px]">
              <span className="text-muted">lucro</span>
              <span
                className={`figure ${(eco.profit ?? 0) > 0 ? "text-up" : "text-down"}`}
              >
                {formatSilver(eco.profit)}
              </span>
            </p>
            <p className="flex justify-between text-[11px]">
              <span className="text-muted">margem</span>
              <span className="figure text-body">{eco.margin_pct?.toFixed(1)}%</span>
            </p>
            <p className="flex justify-between text-[11px]">
              <span className="text-muted">taxas</span>
              <span className="figure text-muted">
                {formatSilver((eco.market_fees ?? 0) + (eco.station_fee ?? 0))}
              </span>
            </p>
          </>
        )}
      </div>
    </article>
  );
}
