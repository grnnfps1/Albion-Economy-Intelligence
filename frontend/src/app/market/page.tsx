import { ColumnHeader } from "@/components/ColumnHeader";
import { PageShell } from "@/components/PageShell";
import { CityTag, QualityBadge, TierBadge } from "@/components/ui/Badges";
import { AgeTag, DenseRow } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchMarketPrices, type MarketPrice, type PriceField } from "@/lib/api";
import { formatSilver } from "@/lib/format";
import { getPreferences } from "@/lib/preferences";

export const dynamic = "force-dynamic";

const COLUNAS =
  "minmax(13rem,1.5fr) 8.5rem 8.5rem 8.5rem 8.5rem 9rem 8rem";

const GRUPOS = [
  {
    chave: "sort_by", padrao: "item",
    opcoes: [
      { valor: "item", rotulo: "item" },
      { valor: "sell_price_min", rotulo: "compra" },
      { valor: "buy_price_max", rotulo: "venda" },
      { valor: "observed_at", rotulo: "coleta" },
    ],
  },
  {
    chave: "tier", padrao: "",
    opcoes: [
      { valor: "", rotulo: "todos" },
      ...[4, 5, 6, 7, 8].map((t) => ({ valor: String(t), rotulo: `T${t}` })),
    ],
  },
  {
    chave: "enchantment", padrao: "",
    opcoes: [
      { valor: "", rotulo: "encanto" },
      ...[0, 1, 2, 3, 4].map((e) => ({ valor: String(e), rotulo: `.${e}` })),
    ],
  },
];

export default async function MarketPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const page = await fetchMarketPrices({ server: prefs.server, ...query, limit: "40" });

  return (
    <PageShell
      titulo="Mercado"
      descricao="Preço fresco num mercado que quase ninguém abre continua sendo preço frágil. Por isso a idade e a cobertura do histórico aparecem em toda linha."
      contagem={page ? `${page.prices.length} de ${formatSilver(page.total)} cotações` : undefined}
      grupos={GRUPOS}
      prefs={prefs}
    >
      <ColumnHeader
        columns={COLUNAS}
        ordemPadrao="item"
        colunas={[
          { rotulo: "item" },
          { rotulo: "você paga", ordenavel: "sell_price_min", alinhamento: "right" },
          { rotulo: "venda máx", alinhamento: "right" },
          { rotulo: "você recebe", ordenavel: "buy_price_max", alinhamento: "right" },
          { rotulo: "compra mín", alinhamento: "right" },
          { rotulo: "mediana 30d", alinhamento: "right" },
          { rotulo: "giro", alinhamento: "right" },
        ]}
      />

      {page === null && <p className="p-4 text-[12px] text-down">A API não respondeu.</p>}

      {page?.total === 0 && (
        <p className="max-w-prose p-4 text-[12px] text-muted leading-relaxed">
          Nenhum preço para este recorte. Pode ser banco vazio — rode a coleta — ou mercado que
          ninguém abriu no jogo. Ausência de cotação não é preço baixo.
        </p>
      )}

      {page?.prices.map((p) => (
        <MarketLine key={`${p.item}-${p.location}-${p.quality}`} price={p} />
      ))}
    </PageShell>
  );
}

function Preco({ campo }: { campo: PriceField }) {
  if (campo.value === null) {
    return (
      <div className="pr-3 text-right">
        <span className="text-[11px] text-dim">sem dado</span>
      </div>
    );
  }
  return (
    <div className="pr-3 text-right">
      <span className="figure text-[12.5px]">{formatSilver(campo.value)}</span>
      <span className="mt-px block">
        <AgeTag seconds={campo.age_seconds} freshness={campo.freshness} />
      </span>
    </div>
  );
}

function MarketLine({ price }: { price: MarketPrice }) {
  const distancia = price.vs_median_pct;
  const liq = price.liquidity;
  const cobertura = liq.status === "KNOWN" ? liq.days_with_data / liq.period_days : 0;

  return (
    <DenseRow tier={price.tier} positive={null} columns={COLUNAS}>
      <div className="flex min-w-0 items-center gap-2.5">
        <ItemIcon url={price.icon_url} alt={price.item_name ?? price.item} tier={price.tier} />
        <div className="min-w-0">
          <div className="mb-[3px] flex flex-wrap gap-1">
            <TierBadge tier={price.tier} enchantment={price.enchantment} />
            <QualityBadge quality={price.quality} />
            <CityTag city={price.location} className="text-[9.5px] text-muted" />
          </div>
          <div className="truncate text-[12.5px] leading-tight" title={price.item}>
            {price.item_name ?? price.item}
          </div>
        </div>
      </div>

      <Preco campo={price.sell_min} />
      <Preco campo={price.sell_max} />
      <Preco campo={price.buy_max} />
      <Preco campo={price.buy_min} />

      <div className="pr-3 text-right">
        <span className="figure text-[12.5px]">
          {price.median_30d === null ? "—" : formatSilver(price.median_30d)}
        </span>
        {distancia !== null && (
          <span
            className={`figure mt-px block text-[9.5px] ${
              distancia <= -5 ? "text-up" : distancia >= 5 ? "text-down" : "text-dim"
            }`}
            title="distância do preço de compra imediata até a mediana"
          >
            {distancia > 0 ? "+" : ""}
            {distancia.toFixed(1)}%
          </span>
        )}
      </div>

      <div className="pr-3 text-right">
        {liq.status === "UNKNOWN" ? (
          <span className="text-[11px] text-dim">desconhecido</span>
        ) : (
          <>
            <span className="figure text-[12px]">
              {formatSilver(liq.units_per_day)}
              <span className="ml-px text-[9px] text-dim">/dia</span>
            </span>
            <span className="mt-[3px] ml-auto block h-[3px] w-12 overflow-hidden rounded-full bg-line">
              <span
                className={`block h-full ${
                  cobertura >= 0.7 ? "bg-up" : cobertura >= 0.3 ? "bg-warn" : "bg-down"
                }`}
                style={{ width: `${cobertura * 100}%` }}
              />
            </span>
          </>
        )}
      </div>
    </DenseRow>
  );
}
