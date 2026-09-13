import type { MarketPrice, PriceField } from "@/lib/api";
import { formatDataAge, formatSilver } from "@/lib/format";

import { CityChip } from "./CityChip";
import { LiquidityBar } from "./LiquidityBar";

const TOM_IDADE: Record<string, string> = {
  ATUALIZADO: "text-up",
  DESATUALIZADO: "text-warn",
  ANTIGO: "text-down",
  DESCONHECIDO: "text-muted",
};

/**
 * Uma linha por item × cidade × qualidade, densa.
 *
 * O agrupamento é o ponto: as duas pontas do mercado ficam em blocos separados
 * e rotulados pelo que significam na prática, não pelo nome do campo na API.
 * "Venda mín" isolado não diz nada; "o que você paga comprando agora" diz.
 */
function Perna({
  titulo,
  legenda,
  principal,
  rotuloPrincipal,
  secundario,
  rotuloSecundario,
}: {
  titulo: string;
  legenda: string;
  principal: PriceField;
  rotuloPrincipal: string;
  secundario: PriceField;
  rotuloSecundario: string;
}) {
  const vazio = principal.value === null && secundario.value === null;

  return (
    <div className="min-w-44 flex-1 border-line border-l pl-3">
      <p className="text-muted text-[11px] uppercase tracking-wide">{titulo}</p>
      <p className="mb-1.5 text-muted text-[11px]">{legenda}</p>

      {vazio ? (
        <p className="text-muted text-xs">sem ordem registrada</p>
      ) : (
        <>
          <p className="flex items-baseline justify-between gap-2">
            <span className="text-muted text-xs">{rotuloPrincipal}</span>
            {principal.value === null ? (
              <span className="text-muted text-xs">sem dado</span>
            ) : (
              <span className="flex items-baseline gap-2">
                <span className="figure text-body text-sm">
                  {formatSilver(principal.value)}
                </span>
                <span className={`figure text-[11px] ${TOM_IDADE[principal.freshness]}`}>
                  {formatDataAge(principal.age_seconds)}
                </span>
              </span>
            )}
          </p>
          <p className="flex items-baseline justify-between gap-2">
            <span className="text-muted text-[11px]">{rotuloSecundario}</span>
            {secundario.value === null ? (
              <span className="text-muted text-[11px]">sem dado</span>
            ) : (
              <span className="flex items-baseline gap-2">
                <span className="figure text-muted text-xs">
                  {formatSilver(secundario.value)}
                </span>
                <span className={`figure text-[11px] ${TOM_IDADE[secundario.freshness]}`}>
                  {formatDataAge(secundario.age_seconds)}
                </span>
              </span>
            )}
          </p>
        </>
      )}
    </div>
  );
}

export function MarketRow({ price }: { price: MarketPrice }) {
  const distancia = price.vs_median_pct;

  return (
    <article className="flex flex-wrap items-stretch gap-4 border-line/60 border-b py-3 last:border-0">
      {/* identidade */}
      <div className="min-w-56 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-1.5">
          <span className="figure rounded-sm border border-line-strong px-1.5 py-0.5 text-[11px] text-body">
            T{price.tier ?? "?"}
            {price.enchantment ? `.${price.enchantment}` : ""}
          </span>
          <span className="figure rounded-sm bg-ink-raised px-1.5 py-0.5 text-[11px] text-muted">
            Q{price.quality}
          </span>
          <CityChip city={price.location} kind={price.location_kind} />
        </div>
        <p className="text-body text-sm leading-tight">{price.item_name ?? price.item}</p>
        <p className="figure text-muted text-[11px]">{price.item}</p>
      </div>

      <Perna
        titulo="Comprando agora"
        legenda="o que você paga"
        principal={price.sell_min}
        rotuloPrincipal="venda mín"
        secundario={price.sell_max}
        rotuloSecundario="venda máx"
      />

      <Perna
        titulo="Vendendo agora"
        legenda="o que você recebe"
        principal={price.buy_max}
        rotuloPrincipal="compra máx"
        secundario={price.buy_min}
        rotuloSecundario="compra mín"
      />

      {/* referência e giro */}
      <div className="min-w-48 flex-1 border-line border-l pl-3">
        <p className="text-muted text-[11px] uppercase tracking-wide">Referência</p>
        <p className="mb-1.5 text-muted text-[11px]">mediana de 30 dias</p>

        <p className="flex items-baseline justify-between gap-2">
          <span className="figure text-body text-sm">
            {price.median_30d === null ? "—" : formatSilver(Math.round(price.median_30d))}
          </span>
          {distancia !== null && (
            <span
              className={`figure text-xs ${
                distancia <= -5 ? "text-up" : distancia >= 5 ? "text-down" : "text-muted"
              }`}
              title="distância do preço de compra imediata até a mediana"
            >
              {distancia > 0 ? "+" : ""}
              {distancia.toFixed(1)}%
            </span>
          )}
        </p>
        <div className="mt-1">
          <LiquidityBar liquidity={price.liquidity} />
        </div>
      </div>
    </article>
  );
}
