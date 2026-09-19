import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { CopyButton } from "@/components/sheet/CopyButton";
import { ExportButton } from "@/components/sheet/ExportButton";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { ReturnTag, TierBadge } from "@/components/ui/Badges";
import { Figure, ProfitFigure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchRefining, type RefiningOpportunity,
  ultimaFalha,
} from "@/lib/api";
import { toExportSheet, type ExportColumn } from "@/lib/export";
import { formatDataAge, formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";
import { tierBorderLeft } from "@/lib/tiers";

export const dynamic = "force-dynamic";

/**
 * Só grandezas de decisão. Duas colunas saíram na fase 19:
 *
 * - **cadeia** ocupava a largura de uma coluna de item para mostrar um caminho
 *   que quase sempre repetia o que o tier já diz. Os elos continuam na
 *   resposta e no balão do custo de produzir;
 * - **idade** virava coluna própria para um dado que cabe numa cor.
 *
 * A idade **não some do produto** — isso seria desfazer uma decisão consciente
 * desde a fase 4. Ela migra para a cor do preço e para o balão: cotação velha
 * continua sendo a diferença entre recomendação e chute.
 */
const COLUNAS: SheetColumn[] = [
  { label: "item", width: "item", left: true },
  { label: "comprar pronto", width: "num", title: "custo do insumo comprado no mercado" },
  { label: "produzir", width: "num", title: "custo de refinar a cadeia inteira" },
  { label: "lucro", width: "num" },
  { label: "prata/focus", width: "num", title: "a ordenação principal" },
  {
    label: "lucro/dia",
    width: "num",
    title:
      "o que um dia desta operação rende, limitado pelo Focus do dia e pelo que o mercado absorve — é o número que compara com a fazenda",
  },
  { label: "focus/un", width: "focus" },
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
  { header: "lucro/dia", value: (o) => o.profit_per_day },
  { header: "unidades/dia", value: (o) => o.units_per_day },
  { header: "trava do dia", value: (o) => o.daily_limiter },
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
      {data === null && <ApiDown falha={ultimaFalha()} />}

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

/**
 * Resumo da cadeia, para o balão da coluna "produzir".
 *
 * A cadeia perdeu a coluna própria na fase 19 — ela ocupava a largura de um
 * item para mostrar um caminho que o tier quase sempre já diz. O conteúdo não
 * se perdeu: ele qualifica exatamente o número de que faz parte, que é o custo
 * de produzir.
 *
 * Inclui a variante descartada quando existe: com token de facção o custo muda
 * bastante, e quem tem token parado no inventário precisa saber que a rota
 * existe mesmo quando o motor escolheu a outra.
 */
function resumoDaCadeia(op: RefiningOpportunity, base: string): string {
  const elos = op.chain.filter((p) => p.craft_cost !== null);
  if (elos.length === 0) return "sem elos calculáveis";

  const linhas = elos.map((passo) => {
    const onde =
      passo.sourcing === "MERCADO"
        ? `comprar em ${passo.location ?? base}${passo.is_alternate_city ? " (outra cidade)" : ""}`
        : "produzir";
    const alternativa =
      passo.alternative_cost === null || passo.alternative_label === null
        ? ""
        : ` · alternativa ${passo.alternative_label}: ${formatSilver(passo.alternative_cost)}`;
    return `${passo.item}: ${onde}${alternativa}`;
  });

  const cidades = op.material_sourcing.cities_involved;
  const espalhamento =
    cidades >= 3 ? `\n${cidades} cidades — cada uma é uma viagem a mais.` : "";

  return linhas.join("\n") + espalhamento;
}

/**
 * Cor da idade, nos mesmos limiares de `AgeTag`.
 *
 * Existe aqui porque a idade deixou de ter coluna própria: ela precisa viver
 * como cor de um rótulo que já existe, sem gastar largura.
 */
function tomDeIdade(segundos: number | null): string {
  if (segundos === null) return "text-dim";
  if (segundos <= 900) return "text-up";
  if (segundos <= 21600) return "text-warn";
  return "text-down";
}

/**
 * O que trava o dia: o Focus ou o mercado.
 *
 * Saber qual é a trava muda a decisão seguinte: adianta subir spec ou adianta
 * procurar outro item? Mesma lição da fase 9.
 */
const TRAVA: Record<string, { texto: string; tom: string; dica: string }> = {
  FOCUS: {
    texto: "focus",
    tom: "text-body",
    dica: "o Focus do dia acaba antes de o mercado saturar — subir spec aumenta o ganho",
  },
  MERCADO: {
    texto: "mercado",
    tom: "text-warn",
    dica: "o mercado satura antes de o Focus acabar — produzir mais não adianta",
  },
  DESCONHECIDO: {
    texto: "—",
    tom: "text-dim",
    dica: "sem giro medido: não dá para saber quanto o mercado absorve num dia",
  },
};

function LucroDia({
  profit,
  units,
  limiter,
  reason,
}: {
  profit: number | null;
  units: number | null;
  limiter: string;
  reason: string | null;
}) {
  const trava = TRAVA[limiter] ?? TRAVA.DESCONHECIDO;
  if (profit === null) {
    return (
      <td title={reason ?? undefined}>
        <span className="text-[10.5px] text-dim">—</span>
      </td>
    );
  }
  const positivo = profit > 0;
  return (
    <td title={trava.dica}>
      <span className={`figure font-semibold text-[13px] ${positivo ? "text-up" : "text-down"}`}>
        {positivo ? "+" : ""}
        {formatSilver(profit)}
      </span>
      <span className={`lbl mt-px block ${trava.tom}`}>
        {units === null ? trava.texto : `${formatSilver(units)} un · ${trava.texto}`}
      </span>
    </td>
  );
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

      {/* A idade perdeu a coluna, não o produto: ela vira a cor do rótulo e o
          balão. Preço de seis horas atrás não é preço. */}
      <td title={`cotação de venda ${formatDataAge(op.sell_age_seconds)}`}>
        <span className="figure text-val">{formatSilver(op.cost_from_market)}</span>
        <span className={`lbl mt-px block ${tomDeIdade(op.sell_age_seconds)}`}>
          {formatDataAge(op.sell_age_seconds)}
        </span>
      </td>
      <td title={resumoDaCadeia(op, base)}>
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

      <LucroDia
        profit={op.profit_per_day}
        units={op.units_per_day}
        limiter={op.daily_limiter}
        reason={op.daily_reason}
      />

      <td className="figure text-[10.5px] text-muted">{formatSilver(op.focus_per_unit)}</td>

      <td className="figure text-[10px] text-dim">
        {op.liquidity_units_per_day === null
          ? "—"
          : `${formatSilver(op.liquidity_units_per_day)}/d`}
      </td>
    </tr>
  );
}
