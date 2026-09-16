import { PageShell } from "@/components/PageShell";
import { ColumnHeader } from "@/components/ColumnHeader";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import {
  CityTag,
  QualityBadge,
  ReturnTag,
  SpreadWarning,
  TierBadge,
  ZoneTag,
} from "@/components/ui/Badges";
import { AgeTag, DenseRow, Figure, RiskProfitFigure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchCrafting, type CraftOpportunity } from "@/lib/api";
import { formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";

export const dynamic = "force-dynamic";

const COLUNAS =
  "minmax(13rem,1.5fr) 7.5rem 7.5rem 8.5rem 7.5rem minmax(15rem,1.8fr) 9.5rem";

const GRUPOS = [
  {
    chave: "sort_by",
    padrao: "profit_per_focus",
    opcoes: [
      { valor: "profit_per_focus", rotulo: "prata/focus" },
      { valor: "profit", rotulo: "lucro" },
      { valor: "roi", rotulo: "ROI" },
    ],
  },
  {
    // Onde comprar cada material. Uma cidade é o padrão porque rota espalhada
    // custa viagem: só vale quando a economia paga o desvio.
    chave: "sourcing_mode",
    padrao: "CIDADE_UNICA",
    opcoes: [
      { valor: "CIDADE_UNICA", rotulo: "uma cidade" },
      { valor: "MAIS_BARATO", rotulo: "mais barato" },
      { valor: "COMPARAR", rotulo: "comparar" },
    ],
  },
  {
    chave: "tier",
    padrao: "",
    opcoes: [
      { valor: "", rotulo: "todos" },
      ...[4, 5, 6, 7, 8].map((t) => ({ valor: String(t), rotulo: `T${t}` })),
    ],
  },
  {
    chave: "station_category",
    padrao: "",
    opcoes: [
      { valor: "", rotulo: "tudo" },
      { valor: "wood", rotulo: "madeira" },
      { valor: "metal", rotulo: "metal" },
      { valor: "leather", rotulo: "couro" },
      { valor: "cloth", rotulo: "tecido" },
    ],
  },
];

export default async function CraftingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const data = await fetchCrafting({
    ...feeParams(prefs),
    buy_location: prefs.buyLocation,
    sell_location: prefs.sellLocation,
    ...query,
    limit: "40",
  });

  return (
    <PageShell
      titulo="Crafting"
      descricao="Prata por focus manda no ranking: focus é o recurso escasso, e um craft que rende mais gastando três vezes mais focus é o pior negócio dos dois."
      contagem={data ? `${data.opportunities.length} de ${data.total} receitas` : undefined}
      grupos={GRUPOS}
      prefs={prefs}
    >
      <ColumnHeader
        columns={COLUNAS}
        ordemPadrao="profit_per_focus"
        colunas={[
          { rotulo: "item" },
          { rotulo: "você gasta", alinhamento: "right" },
          { rotulo: "você recebe", alinhamento: "right" },
          { rotulo: "lucro ajustado", ordenavel: "profit", alinhamento: "right" },
          { rotulo: "prata / focus", ordenavel: "profit_per_focus", alinhamento: "right" },
          { rotulo: "materiais · onde comprar" },
          { rotulo: "vender em", alinhamento: "right" },
        ]}
      />

      {data === null && (
        <ApiDown />
      )}

      {data?.total === 0 && (
        <EmptyState>
          Nenhuma receita com dados suficientes. O custo precisa de cotação de cada material em{" "}
          {prefs.buyLocation}. Rode a coleta ou tente outra cidade nas preferências.
        </EmptyState>
      )}

      {data?.opportunities.map((op) => (
        <CraftLine key={`${op.item}-${op.recipe_variant}`} op={op} />
      ))}

      {data && data.opportunities.length > 0 && (
        <p className="max-w-prose p-4 text-[11px] text-dim leading-relaxed">
          <b>Como ler:</b> <i>você gasta</i> é o custo dos materiais depois do retorno, mais a
          taxa da estação. <i>Você recebe</i> já desconta o imposto de venda. Nos materiais, o
          número é o preço por unidade; o badge no ícone é a quantidade. A faixa à esquerda é o
          tier. Material com moldura âmbar vem de outra cidade — e o aviso de cidades aparece a
          partir da terceira, porque economia espalhada por quatro mercados custa quatro viagens.
          Vender fora da cidade onde se compra cria uma rota, e rota tem zona: qualquer ponta em
          Caerleon ou no Black Market atravessa <b className="text-down">vermelha/preta</b>, onde
          a carga inteira pode não chegar. O Black Market aceita equipamento, nunca recurso.
          A marca <i>↩</i> é o retorno de material: ele muda com a cidade, e craftar na cidade
          com bônus da família devolve 24,8% do material em vez de 15,2%.
        </p>
      )}
    </PageShell>
  );
}

/**
 * Tooltip do material: preço, e o que o desvio de cidade compra.
 *
 * O rótulo diz a consequência, não o nome do campo: "economiza X contra
 * Caerleon" responde a pergunta que "cidade alternativa" só levanta.
 */
function titulo(m: CraftOpportunity["materials"][number], base: string): string {
  const linha = `${m.item_name ?? m.item}: ${m.quantity} × ${formatSilver(m.unit_price)} = ${formatSilver(m.total_price)}`;
  if (!m.is_alternate_city) return linha;
  if (m.savings_vs_base === null) {
    return `${linha} · ${base} não tem cotação deste material; só ${m.location} tem.`;
  }
  return `${linha} · comprando em ${m.location} você economiza ${formatSilver(m.savings_vs_base)} contra ${base}.`;
}

function CraftLine({ op }: { op: CraftOpportunity }) {
  const eco = op.economics;
  const positivo = eco.known ? (eco.profit ?? 0) > 0 : null;

  return (
    <DenseRow tier={op.tier} positive={positivo} columns={COLUNAS}>
      <div className="flex min-w-0 items-center gap-2.5">
        <ItemIcon url={op.icon_url} alt={op.item_name ?? op.item} tier={op.tier} />
        <div className="min-w-0">
          <div className="mb-[3px] flex gap-1">
            <TierBadge tier={op.tier} enchantment={op.enchantment} />
            <QualityBadge quality={1} />
          </div>
          <div className="truncate text-[12.5px] leading-tight" title={op.item}>
            {op.item_name ?? op.item}
          </div>
          <div className="mt-[3px]">
            <ReturnTag
              rate={op.material_return.rate}
              isBestCity={op.material_return.is_best_city}
              bestCityName={op.material_return.best_city_name}
              delta={op.material_return.delta}
              mappingKnown={op.material_return.mapping_known}
            />
          </div>
        </div>
      </div>

      <Figure value={eco.material_cost_net} label="materiais + taxas" />
      <Figure value={eco.sale_revenue_net} label="após imposto" />
      <RiskProfitFigure
        grossProfit={eco.profit}
        expectedProfit={op.risk.expected_profit}
        lossProbability={op.risk.loss_probability}
        crossesOpenWorld={op.risk.crosses_open_world}
        marginPct={eco.margin_pct}
        unknownReason={eco.reason}
      />

      <div className="pr-3 text-right">
        <span
          className={`figure font-semibold text-[13.5px] ${
            positivo ? "text-up" : positivo === false ? "text-down" : "text-dim"
          }`}
        >
          {eco.profit_per_focus === null ? "—" : formatSilver(eco.profit_per_focus)}
        </span>
        <span className="mt-px block text-[9px] text-dim uppercase tracking-[0.05em]">
          {formatSilver(eco.focus_cost)} focus
        </span>
      </div>

      <div className="flex items-center gap-1.5 overflow-hidden">
        {op.materials.map((m) => (
          <span
            key={m.item}
            title={titulo(m, op.buy_location)}
            className={`flex shrink-0 items-center gap-1.5 rounded border bg-raised px-1.5 py-[3px] ${
              m.is_alternate_city ? "border-warn/40" : "border-line"
            }`}
          >
            <ItemIcon url={m.icon_url} alt={m.item} tier={op.tier} quantity={m.quantity} size={28} />
            <span className="flex flex-col leading-[1.15]">
              <span className="figure text-[11px]">
                {formatSilver(m.unit_price)}
                <span className="ml-px text-[9px] text-dim">/un</span>
              </span>
              <CityTag
                city={m.location ?? "—"}
                alternate={m.is_alternate_city}
                className="text-[9.5px] text-muted"
              />
            </span>
          </span>
        ))}
        <SpreadWarning
          cities={op.material_sourcing.cities_involved}
          savings={op.material_sourcing.savings}
          savingsPct={op.material_sourcing.savings_pct}
        />
      </div>

      <div className="text-right">
        <CityTag city={op.sell_location} className="justify-end text-[12px]" />
        <div className="mt-[3px] flex justify-end">
          <ZoneTag zone={op.risk.zone} label={op.risk.zone_label} />
        </div>
        <div className="mt-px flex justify-end gap-1.5">
          <AgeTag seconds={op.sell_age_seconds} />
          <span className="figure text-[9.5px] text-dim">
            {op.liquidity_units_per_day === null
              ? "giro ?"
              : `${formatSilver(op.liquidity_units_per_day)}/dia`}
          </span>
        </div>
      </div>
    </DenseRow>
  );
}
