import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { CopyButton } from "@/components/sheet/CopyButton";
import { ExportButton } from "@/components/sheet/ExportButton";
import { HoverTip } from "@/components/sheet/HoverTip";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { CityTag, ReturnTag, SpreadWarning, TierBadge } from "@/components/ui/Badges";
import { AgeTag, Figure, ProfitFigure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchRefining, type RefiningOpportunity } from "@/lib/api";
import { toExportSheet, type ExportColumn } from "@/lib/export";
import { formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";
import { tierBorderLeft } from "@/lib/tiers";

export const dynamic = "force-dynamic";

/**
 * A cadeia fica numa coluna só, e é a exceção consciente ao "uma coluna por
 * grandeza": ela não é uma grandeza, é um caminho de comprimento variável —
 * T2→T8 são sete elos. Abrir sete colunas encheria a tabela de traço para as
 * linhas de T4. As grandezas de decisão, essas sim, ganham cada uma a sua.
 */
const COLUNAS: SheetColumn[] = [
  { label: "item", width: "item", left: true },
  { label: "comprar pronto", width: "num", title: "custo do insumo comprado no mercado" },
  { label: "produzir", width: "num", title: "custo de refinar a cadeia inteira" },
  { label: "lucro", width: "num" },
  { label: "prata/focus", width: "num", title: "a ordenação principal" },
  { label: "focus/un", width: "focus" },
  { label: "cadeia · onde está o gargalo", width: "item", left: true },
  { label: "idade", width: "mini" },
  { label: "giro", width: "mini" },
];

const EXPORTACAO: ExportColumn<RefiningOpportunity>[] = [
  { header: "imagem", value: (o) => o.icon_url, image: true },
  { header: "id", value: (o) => o.item },
  { header: "nome", value: (o) => o.item_name },
  { header: "tier", value: (o) => o.tier },
  { header: "encanto", value: (o) => o.enchantment },
  { header: "família", value: (o) => o.family },
  { header: "origem do insumo", value: (o) => o.sourcing },
  { header: "custo unitário", value: (o) => o.unit_cost },
  { header: "comprar pronto", value: (o) => o.cost_from_market },
  { header: "produzir", value: (o) => o.cost_from_crafting },
  { header: "preço de venda", value: (o) => o.sell_price },
  { header: "lucro", value: (o) => o.profit },
  { header: "margem %", value: (o) => o.margin_pct },
  { header: "prata/focus", value: (o) => o.profit_per_focus },
  { header: "focus/un", value: (o) => o.focus_per_unit },
  { header: "retorno", value: (o) => o.material_return.rate },
  { header: "melhor cidade p/ retorno", value: (o) => o.material_return.best_city_name },
  { header: "cidades envolvidas", value: (o) => o.material_sourcing.cities_involved },
  { header: "economia espalhando", value: (o) => o.material_sourcing.savings },
  // A cadeia em texto: numa planilha ela é referência, não coluna de cálculo.
  {
    header: "cadeia",
    value: (o) =>
      o.chain
        .filter((p) => p.craft_cost !== null)
        .map((p) => `${p.item}=${p.sourcing}`)
        .join(" | "),
  },
  { header: "giro/dia", value: (o) => o.liquidity_units_per_day },
  { header: "idade venda (s)", value: (o) => o.sell_age_seconds },
  { header: "motivo do desconhecido", value: (o) => o.reason },
];

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
      acoes={
        <ExportButton
          sheet={toExportSheet(data?.opportunities ?? [], EXPORTACAO)}
          screen="refino"
          filters={{
            familia: query.family,
            origem: query.sourcing,
            cidades: query.sourcing_mode,
            compra: prefs.buyLocation,
            venda: prefs.sellLocation,
          }}
        />
      }
    >
      {data === null && <ApiDown />}

      {data?.total === 0 && (
        <EmptyState>
          Nenhum recurso refinado com dados suficientes. Um tier sem cotação interrompe o cálculo
          dos tiers acima dele.
        </EmptyState>
      )}

      {data && data.total > 0 && (
        <SheetTable columns={COLUNAS}>
          {data.opportunities.map((op) => (
            <RefiningLine key={op.item} op={op} base={data.buy_location} />
          ))}
        </SheetTable>
      )}

      {data && data.opportunities.length > 0 && (
        <p className="max-w-prose p-4 text-[11px] text-dim leading-relaxed">
          Cada elo da cadeia paga a taxa da estação, não só o último — em refino isso pesa muito
          mais que em craft avulso. As duas colunas de custo são as duas respostas certas: quem
          compra tudo pronto olha a primeira, quem já tem a cadeia montada olha a segunda. O elo
          com moldura âmbar é comprado fora da cidade base; o aviso de cidades aparece a partir da
          terceira, porque cada cidade a mais é uma viagem a mais. A marca <i>↩</i> é o retorno
          de material, e ele segue o <b>recurso</b>: minério rende 36,7% em Thetford e 15,2% em
          qualquer outra cidade. A diferença é maior que a que o Focus dá sozinho.
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

  const tinta =
    positivo === true
      ? "bg-[linear-gradient(90deg,rgba(86,192,127,0.08),transparent_32%)]"
      : positivo === false
        ? "bg-[linear-gradient(90deg,rgba(226,85,92,0.08),transparent_32%)]"
        : "";

  return (
    <tr className={tinta}>
      <td className={`l ${tierBorderLeft(op.tier)}`}>
        <span className="flex min-w-0 items-center gap-2">
          <ItemIcon url={op.icon_url} alt={op.item_name ?? op.item} tier={op.tier} size={22} />
          <span className="min-w-0">
            <span className="flex items-center gap-1">
              <TierBadge tier={op.tier} enchantment={op.enchantment} />
              {op.family && (
                <span className="figure rounded-[3px] border border-line bg-raised px-[5px] py-px text-[9.5px] text-muted">
                  {op.family.toLowerCase()}
                </span>
              )}
              <ReturnTag
                rate={op.material_return.rate}
                isBestCity={op.material_return.is_best_city}
                bestCityName={op.material_return.best_city_name}
                delta={op.material_return.delta}
                mappingKnown={op.material_return.mapping_known}
              />
            </span>
            <span className="flex min-w-0 items-center">
              <span className="truncate">{op.item_name ?? op.item}</span>
              <CopyButton name={op.item_name} id={op.item} />
            </span>
            <span className="block truncate text-[9px] text-dim">{op.item}</span>
          </span>
        </span>
      </td>

      <td>
        <Figure value={op.cost_from_market} label="no mercado" />
      </td>
      <td>
        <Figure value={op.cost_from_crafting} label="a cadeia toda" />
      </td>
      <td>
        <ProfitFigure
          profit={op.profit}
          marginPct={op.margin_pct}
          unknownReason={op.reason}
        />
      </td>

      <td>
        <span
          className={`figure font-semibold text-[13px] ${
            positivo ? "text-up" : positivo === false ? "text-down" : "text-dim"
          }`}
        >
          {op.profit_per_focus === null ? "—" : formatSilver(op.profit_per_focus)}
        </span>
      </td>

      <td className="figure text-[10.5px] text-muted">{formatSilver(op.focus_per_unit)}</td>

      <td className="l">
        <span className="flex flex-wrap items-center gap-1">
          {elos.length === 0 ? (
            <span className="text-[10.5px] text-dim">sem elos calculáveis</span>
          ) : (
            elos.map((passo) => (
              <HoverTip key={passo.item} dica={titulo(passo, base)}>
                <span
                  className={`figure inline-flex shrink-0 items-center gap-[4px] rounded-[3px] border px-[4px] py-px text-[9px] ${
                    passo.sourcing !== "MERCADO"
                      ? "border-up/30 bg-up/10 text-up"
                      : passo.is_alternate_city
                        ? "border-warn/40 bg-raised text-muted"
                        : "border-line bg-raised text-muted"
                  }`}
                >
                  {passo.item.split("_")[0]}{" "}
                  {passo.sourcing === "MERCADO" ? "comprar" : "produzir"}
                  {passo.sourcing === "MERCADO" && passo.location && (
                    <CityTag city={passo.location} alternate={passo.is_alternate_city} />
                  )}
                </span>
              </HoverTip>
            ))
          )}
          <SpreadWarning
            cities={op.material_sourcing.cities_involved}
            savings={op.material_sourcing.savings}
            savingsPct={op.material_sourcing.savings_pct}
          />
        </span>
      </td>

      <td>
        <AgeTag seconds={op.sell_age_seconds} />
      </td>

      <td className="figure text-[10px] text-dim">
        {op.liquidity_units_per_day === null
          ? "—"
          : `${formatSilver(op.liquidity_units_per_day)}/d`}
      </td>
    </tr>
  );
}
