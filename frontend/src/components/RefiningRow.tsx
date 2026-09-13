import type { RefiningOpportunity } from "@/lib/api";
import { formatDataAge, formatSilver } from "@/lib/format";

import { ItemIcon } from "./ItemIcon";

const TOM_IDADE = (s: number | null) =>
  s === null ? "text-muted" : s <= 900 ? "text-up" : s <= 21600 ? "text-warn" : "text-down";

export function RefiningRow({ opportunity }: { opportunity: RefiningOpportunity }) {
  const mercado = opportunity.cost_from_market;
  const producao = opportunity.cost_from_crafting;
  // Diferença entre as duas formas de custear o insumo. É o número que responde
  // "vale a pena manter a cadeia montada?".
  const diferenca =
    mercado !== null && producao !== null && mercado > 0
      ? ((producao - mercado) / mercado) * 100
      : null;

  // Só os elos que são decisão do jogador: o recurso bruto sempre vem do mercado.
  const elos = opportunity.chain.filter((passo) => passo.craft_cost !== null);

  return (
    <article className="flex flex-wrap items-stretch gap-4 border-line/60 border-b py-3 last:border-0">
      <div className="flex min-w-48 flex-1 gap-3">
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
            {opportunity.family && (
              <span className="rounded-sm bg-ink-raised px-1.5 py-0.5 text-[11px] text-muted">
                {opportunity.family.toLowerCase()}
              </span>
            )}
          </div>
          <p className="truncate text-body text-sm leading-tight">
            {opportunity.item_name ?? opportunity.item}
          </p>
          <p className="figure truncate text-muted text-[11px]">{opportunity.item}</p>
        </div>
      </div>

      {/* comprar pronto vs produzir */}
      <div className="min-w-52 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Custo do insumo</p>
        <p className="mb-1.5 text-muted text-[11px]">as duas respostas</p>

        <p className="flex justify-between text-[11px]">
          <span className="text-muted">comprar pronto</span>
          <span className="figure text-body">{formatSilver(mercado)}</span>
        </p>
        <p className="flex justify-between text-[11px]">
          <span className="text-muted">produzir a cadeia</span>
          <span className="figure text-body">{formatSilver(producao)}</span>
        </p>
        {diferenca !== null && (
          <p className="mt-1 flex justify-between border-line border-t pt-1 text-[11px]">
            <span className="text-muted">produzir sai</span>
            <span className={`figure ${diferenca < 0 ? "text-up" : "text-down"}`}>
              {diferenca < 0 ? "" : "+"}
              {diferenca.toFixed(1)}%
            </span>
          </p>
        )}
      </div>

      {/* a cadeia */}
      <div className="min-w-48 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Cadeia</p>
        <p className="mb-1.5 text-muted text-[11px]">onde está o gargalo</p>

        {elos.length === 0 ? (
          <p className="text-muted text-xs">sem elos calculáveis</p>
        ) : (
          elos.map((passo) => (
            <div key={passo.item} className="mb-0.5 flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-1.5">
                <ItemIcon url={passo.icon_url} alt={passo.item} size={20} />
                <span className="figure truncate text-[11px] text-muted">{passo.item}</span>
              </span>
              <span
                className={`shrink-0 rounded-sm px-1 text-[10px] ${
                  passo.sourcing === "MERCADO" ? "bg-ink-raised text-muted" : "bg-up/15 text-up"
                }`}
                title={
                  passo.sourcing === "MERCADO"
                    ? "mais barato comprar pronto"
                    : "mais barato produzir"
                }
              >
                {passo.sourcing === "MERCADO" ? "comprar" : "produzir"}
              </span>
            </div>
          ))
        )}
      </div>

      {/* resultado */}
      <div className="min-w-44 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Resultado</p>
        <p className="mb-1.5 text-muted text-[11px]">por unidade refinada</p>

        {!opportunity.known ? (
          <div className="rounded-sm border border-line-strong border-dashed px-2 py-1.5">
            <p className="figure text-muted text-xs">UNKNOWN</p>
            <p className="mt-0.5 text-[11px] text-muted leading-snug">{opportunity.reason}</p>
          </div>
        ) : (
          <>
            <p
              className={`figure text-lg ${
                (opportunity.profit ?? 0) > 0 ? "text-up" : "text-down"
              }`}
            >
              {(opportunity.profit ?? 0) > 0 ? "+" : ""}
              {formatSilver(opportunity.profit)}
            </p>
            <p className="flex justify-between text-[11px]">
              <span className="text-muted">margem</span>
              <span className="figure text-body">{opportunity.margin_pct?.toFixed(1)}%</span>
            </p>
            <p className="flex justify-between text-[11px]">
              <span className="text-muted">prata/focus</span>
              <span className="figure text-body">
                {opportunity.profit_per_focus === null
                  ? "sem focus"
                  : formatSilver(opportunity.profit_per_focus)}
              </span>
            </p>
            <p className="flex justify-between text-[11px]">
              <span className="text-muted">venda</span>
              <span className="flex gap-1.5">
                <span className="figure text-body">{formatSilver(opportunity.sell_price)}</span>
                <span className={`figure ${TOM_IDADE(opportunity.sell_age_seconds)}`}>
                  {formatDataAge(opportunity.sell_age_seconds)}
                </span>
              </span>
            </p>
          </>
        )}
      </div>
    </article>
  );
}
