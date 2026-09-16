import { ColumnHeader } from "@/components/ColumnHeader";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { CityTag, SpreadWarning, TierBadge } from "@/components/ui/Badges";
import { AgeTag, DenseRow, Figure, ProfitFigure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchRefining, type RefiningOpportunity } from "@/lib/api";
import { formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";

export const dynamic = "force-dynamic";

const COLUNAS = "minmax(12rem,1.3fr) 8.5rem 8.5rem 9rem 7.5rem minmax(12rem,1.4fr) 7rem";

const GRUPOS = [
  {
    chave: "sourcing", padrao: "MAIS_BARATO",
    opcoes: [
      { valor: "MAIS_BARATO", rotulo: "mais barato por elo" },
      { valor: "MERCADO", rotulo: "comprar pronto" },
      { valor: "PRODUZIR", rotulo: "produzir a cadeia" },
    ],
  },
  {
    // Escolha independente da de cima: aquela decide comprar ou produzir o elo,
    // esta decide em qual cidade comprar o que for comprado.
    chave: "sourcing_mode", padrao: "CIDADE_UNICA",
    opcoes: [
      { valor: "CIDADE_UNICA", rotulo: "uma cidade" },
      { valor: "MAIS_BARATO", rotulo: "mais barato" },
      { valor: "COMPARAR", rotulo: "comparar" },
    ],
  },
  {
    chave: "family", padrao: "",
    opcoes: [
      { valor: "", rotulo: "todas" },
      { valor: "PLANKS", rotulo: "tábuas" },
      { valor: "METALBAR", rotulo: "barras" },
      { valor: "LEATHER", rotulo: "couro" },
      { valor: "CLOTH", rotulo: "tecido" },
      { valor: "STONEBLOCK", rotulo: "blocos" },
    ],
  },
];

export default async function RefiningPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const data = await fetchRefining({
    ...feeParams(prefs),
    buy_location: prefs.buyLocation,
    sell_location: prefs.sellLocation,
    ...query,
    limit: "40",
  });

  return (
    <PageShell
      titulo="Refinamento"
      descricao="Refino encadeia: T5 precisa de T4, que precisa de T3. A pergunta não é “vale refinar T5?” e sim onde na cadeia está o gargalo — e se o insumo anterior sai mais barato comprando pronto ou produzindo."
      contagem={data ? `${data.opportunities.length} de ${data.total} recursos` : undefined}
      grupos={GRUPOS}
      busca={false}
      prefs={prefs}
    >
      <ColumnHeader
        columns={COLUNAS}
        ordemPadrao="profit_per_focus"
        colunas={[
          { rotulo: "item" },
          { rotulo: "comprar pronto", alinhamento: "right" },
          { rotulo: "produzir", alinhamento: "right" },
          { rotulo: "lucro", alinhamento: "right" },
          { rotulo: "prata / focus", alinhamento: "right" },
          { rotulo: "cadeia · onde está o gargalo" },
          { rotulo: "dado", alinhamento: "right" },
        ]}
      />

      {data === null && <ApiDown />}

      {data?.total === 0 && (
        <EmptyState>
          Nenhum recurso refinado com dados suficientes. Um tier sem cotação interrompe o cálculo
          dos tiers acima dele.
        </EmptyState>
      )}

      {data?.opportunities.map((op) => (
        <RefiningLine key={op.item} op={op} base={data.buy_location} />
      ))}

      {data && data.opportunities.length > 0 && (
        <p className="max-w-prose p-4 text-[11px] text-dim leading-relaxed">
          Cada elo da cadeia paga a taxa da estação, não só o último — em refino isso pesa muito
          mais que em craft avulso. As duas colunas de custo são as duas respostas certas: quem
          compra tudo pronto olha a primeira, quem já tem a cadeia montada olha a segunda. O elo
          com moldura âmbar é comprado fora da cidade base; o aviso de cidades aparece a partir da
          terceira, porque cada cidade a mais é uma viagem a mais.
        </p>
      )}
    </PageShell>
  );
}

/** Tooltip do elo: as duas alternativas de custo e o que a cidade muda. */
function titulo(passo: RefiningOpportunity["chain"][number], base: string): string {
  const linha = `${passo.item}: mercado ${formatSilver(passo.market_price)} · produzir ${formatSilver(passo.craft_cost)}`;
  if (passo.sourcing !== "MERCADO" || !passo.is_alternate_city) return linha;
  if (passo.savings_vs_base === null) {
    return `${linha} · ${base} não tem cotação deste elo; só ${passo.location} tem.`;
  }
  return `${linha} · comprando em ${passo.location} você economiza ${formatSilver(passo.savings_vs_base)} por unidade contra ${base}.`;
}

function RefiningLine({ op, base }: { op: RefiningOpportunity; base: string }) {
  const positivo = op.known ? (op.profit ?? 0) > 0 : null;
  const elos = op.chain.filter((p) => p.craft_cost !== null);

  return (
    <DenseRow tier={op.tier} positive={positivo} columns={COLUNAS}>
      <div className="flex min-w-0 items-center gap-2.5">
        <ItemIcon url={op.icon_url} alt={op.item_name ?? op.item} tier={op.tier} />
        <div className="min-w-0">
          <div className="mb-[3px] flex gap-1">
            <TierBadge tier={op.tier} enchantment={op.enchantment} />
            {op.family && (
              <span className="figure rounded-[3px] border border-line bg-raised px-[5px] py-px text-[9.5px] text-muted">
                {op.family.toLowerCase()}
              </span>
            )}
          </div>
          <div className="truncate text-[12.5px] leading-tight" title={op.item}>
            {op.item_name ?? op.item}
          </div>
        </div>
      </div>

      <Figure value={op.cost_from_market} label="no mercado" />
      <Figure value={op.cost_from_crafting} label="a cadeia toda" />
      <ProfitFigure profit={op.profit} marginPct={op.margin_pct} unknownReason={op.reason} />

      <div className="pr-3 text-right">
        <span
          className={`figure font-semibold text-[13.5px] ${
            positivo ? "text-up" : positivo === false ? "text-down" : "text-dim"
          }`}
        >
          {op.profit_per_focus === null ? "—" : formatSilver(op.profit_per_focus)}
        </span>
        <span className="mt-px block text-[9px] text-dim uppercase tracking-[0.05em]">
          {formatSilver(op.focus_per_unit)} focus/un
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-1 overflow-hidden">
        {elos.length === 0 ? (
          <span className="text-[11px] text-dim">sem elos calculáveis</span>
        ) : (
          elos.map((passo) => (
            <span
              key={passo.item}
              title={titulo(passo, base)}
              className={`figure inline-flex shrink-0 items-center gap-[5px] rounded-[3px] border px-[5px] py-px text-[9.5px] ${
                passo.sourcing !== "MERCADO"
                  ? "border-up/30 bg-up/10 text-up"
                  : passo.is_alternate_city
                    ? "border-warn/40 bg-raised text-muted"
                    : "border-line bg-raised text-muted"
              }`}
            >
              {passo.item.split("_")[0]} {passo.sourcing === "MERCADO" ? "comprar" : "produzir"}
              {passo.sourcing === "MERCADO" && passo.location && (
                <CityTag city={passo.location} alternate={passo.is_alternate_city} />
              )}
            </span>
          ))
        )}
        <SpreadWarning
          cities={op.material_sourcing.cities_involved}
          savings={op.material_sourcing.savings}
          savingsPct={op.material_sourcing.savings_pct}
        />
      </div>

      <div className="pr-3 text-right">
        <AgeTag seconds={op.sell_age_seconds} />
        <span className="figure mt-px block text-[9.5px] text-dim">
          {op.liquidity_units_per_day === null
            ? "giro ?"
            : `${formatSilver(op.liquidity_units_per_day)}/dia`}
        </span>
      </div>
    </DenseRow>
  );
}
