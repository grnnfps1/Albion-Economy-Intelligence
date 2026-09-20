import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { Sub } from "@/components/sheet/Chrome";
import { ComoLer } from "@/components/sheet/ComoLer";
import { Aviso, Param, ParamStrip, ParamsDeTaxa } from "@/components/sheet/Chrome";
import { CopyButton } from "@/components/sheet/CopyButton";
import { SHEET_ICON } from "@/components/sheet/Chrome";
import { ExportButton } from "@/components/sheet/ExportButton";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { TierBadge } from "@/components/ui/Badges";
import { Figure } from "@/components/ui/Figures";
import { ProfitFigure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchFocus, type FocusPlan,
  ultimaFalha,
} from "@/lib/api";
import { toExportSheet, type ExportColumn } from "@/lib/export";
import { formatSilver, formatSilverCompact } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";
import { tierBorderLeft } from "@/lib/tiers";

export const dynamic = "force-dynamic";

/** A ordenação de abertura: o que se leva para casa, não a taxa. */
const ORDEM_PADRAO = { by: "realizable_profit", dir: "desc" };

const COLUNAS: SheetColumn[] = [
  { label: "item", width: "item", left: true },
  { label: "prata/focus", width: "num", sortKey: "profit_per_focus",
    title: "a taxa: quanto rende cada ponto de focus" },
  { label: "focus/un", width: "focus" },
  { label: "cabe no focus", width: "num", title: "quantas unidades o orçamento de focus paga" },
  { label: "mercado escoa", width: "num", title: "quantas unidades o giro absorve no horizonte" },
  // `numWide` pelo mesmo motivo do "lucro ajustado" em /crafting: com a seta
  // de ordenação o rótulo não cabe em 6,8rem, e rótulo truncado num
  // cabeçalho clicável é pior que noutro lugar — ele é o alvo do clique.
  { label: "ganho realizável", width: "numWide", sortKey: "realizable_profit",
    title: "o que se leva para casa, não a taxa" },
  { label: "quanto fazer", width: "num" },
  { label: "trava", width: "focus", title: "o que limita: o focus ou o mercado" },
];

const EXPORTACAO: ExportColumn<FocusPlan>[] = [
  { header: "imagem", value: (p) => p.icon_url, image: true },
  { header: "id", value: (p) => p.item },
  { header: "nome", value: (p) => p.item_name },
  { header: "tier", value: (p) => p.tier },
  { header: "encanto", value: (p) => p.enchantment },
  { header: "rota", value: (p) => p.route },
  { header: "prata/focus", value: (p) => p.profit_per_focus },
  { header: "focus/un", value: (p) => p.focus_per_unit },
  { header: "cabe no focus", value: (p) => p.units_by_focus },
  { header: "mercado escoa", value: (p) => p.units_by_liquidity },
  { header: "quanto fazer", value: (p) => p.units },
  { header: "ganho realizável", value: (p) => p.realizable_profit },
  { header: "dias para escoar", value: (p) => p.days_to_sell },
  { header: "trava", value: (p) => p.limiter },
];

const GRUPOS = [
  {
    chave: "horizon_days", padrao: "7",
    opcoes: [1, 3, 7, 14, 30].map((d) => ({ valor: String(d), rotulo: `${d}d` })),
  },
];

const LIMITADOR: Record<string, { texto: string; tom: string; dica: string }> = {
  FOCUS: {
    texto: "focus", tom: "border-line-strong text-body",
    dica: "dá para vender mais do que dá para produzir",
  },
  LIQUIDEZ: {
    texto: "mercado", tom: "border-warn/40 bg-warn/10 text-warn",
    dica: "dá para produzir mais do que dá para escoar",
  },
  DESCONHECIDO: {
    texto: "giro ?", tom: "border-line text-dim",
    dica: "sem histórico suficiente para saber se o mercado absorve",
  },
};

export default async function FocusPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const data = await fetchFocus({
    ...feeParams(prefs),
    buy_location: prefs.buyLocation,
    sell_location: prefs.sellLocation,
    focus_budget: String(prefs.focusBudget),
    ...query,
    limit: "40",
  });

  return (
    <PageShell
      titulo="Focus"
      descricao={`Prata por focus é uma taxa, não um ganho. Com ${formatSilver(prefs.focusBudget)} de focus, o que você leva para casa é limitado também pelo que o mercado absorve — escoar milhares de unidades de algo que gira 3 por dia leva anos.`}
      contagem={data ? `${data.plans.length} de ${data.total} operações` : undefined}
      grupos={GRUPOS}
      busca={false}
      prefs={prefs}
      acoes={
        <ExportButton
          sheet={toExportSheet(data?.plans ?? [], EXPORTACAO)}
          screen="focus"
          filters={{
            ordem: query.sort_by,
            horizonte: query.horizon_days ?? "7",
            orcamento: prefs.focusBudget,
          }}
        />
      }
    >
      {data === null && <ApiDown falha={ultimaFalha()} />}

      {data?.total === 0 && (
        <EmptyState>
          Nenhuma operação com focus e dados suficientes.
        </EmptyState>
      )}

      {data && !data.params.complete && (
        <Aviso>
          Falta configurar: {data.params.missing.join(", ")}. Sem esses valores as linhas
          respondem <b>desconhecido</b> em vez de calcular com zero.
        </Aviso>
      )}

      {data && data.total > 0 && (
        <ParamStrip>
          <Param rotulo="orçamento"
            valor={data.focus_budget === null ? "não informado" : `${formatSilver(data.focus_budget)} focus`}
            tom={data.focus_budget === null ? "warn" : undefined}
            dica="o estoque que limita quanto dá para produzir" />
          <Param rotulo="horizonte" valor={`${data.horizon_days} d`}
            dica="a janela em que o mercado precisa absorver o que se produzir" />
          <ParamsDeTaxa fees={data.params.fees} />
        </ParamStrip>
      )}

      {data && data.total > 0 && (
        <SheetTable
          columns={COLUNAS}
          sort={{ by: data.sort_by, dir: data.sort_dir }}
          sortDefault={ORDEM_PADRAO}
        >
          {data.plans.map((plano) => (
            <FocusLine key={plano.item} plano={plano} dias={data.horizon_days} />
          ))}
        </SheetTable>
      )}

      {data && data.plans.length > 0 && (
        <ComoLer>
          <p className="max-w-prose p-4 text-note text-dim leading-relaxed">
            Troque a ordenação para “prata/focus” e compare: a taxa mais alta nem sempre é o maior
            ganho, porque o item com melhor taxa costuma ser o que menos gira.
          </p>
        </ComoLer>
      )}
    </PageShell>
  );
}

function FocusLine({ plano, dias }: { plano: FocusPlan; dias: number }) {
  const positivo = (plano.realizable_profit ?? 0) > 0;
  const trava = LIMITADOR[plano.limiter] ?? LIMITADOR.DESCONHECIDO;

  const tinta = positivo
    ? "lucro"
    : "prejuizo";

  return (
    <tr className={tinta}>
      <td className={`l ${tierBorderLeft(plano.tier)}`}>
        <span className="flex min-w-0 items-center gap-2">
          <ItemIcon
            url={plano.icon_url}
            alt={plano.item_name ?? plano.item}
            tier={plano.tier}
            size={SHEET_ICON.linha}
          />
          <span className="min-w-0">
            <span className="flex items-center gap-1">
              <TierBadge tier={plano.tier} enchantment={plano.enchantment} />
              <span className="figure rounded-sm border border-line bg-raised px-1.5 py-px text-micro text-muted">
                {plano.route.toLowerCase()}
              </span>
            </span>
            <span className="flex min-w-0 items-center">
              {/* Nome visual manda, id técnico no tooltip — a regra do briefing do
                  redesign. O id saiu da segunda linha: ele não decide nada, e
                  ocupava uma linha inteira da célula mais estreita da tabela.
                  Continua a um hover daqui, e no alt+clique do botão copiar. */}
              <span className="truncate" title={plano.item}>
                {plano.item_name ?? plano.item}
              </span>
              <CopyButton name={plano.item_name} id={plano.item} />
            </span>
          </span>
        </span>
      </td>

      <td className="figure font-semibold text-val">
        {plano.profit_per_focus === null ? "—" : formatSilver(plano.profit_per_focus)}
      </td>

      <td className="figure text-aux text-muted">{formatSilver(plano.focus_per_unit)}</td>

      <td>
        <Figure value={plano.units_by_focus} label="unidades" />
      </td>
      <td>
        <Figure value={plano.units_by_liquidity} label={`em ${dias}d`} />
      </td>

      <td>
        {/* `ProfitFigure` compartilhado. `/focus` não tem margem — o plano é
            sobre quanto se leva para casa no horizonte, não sobre proporção —,
            então a pílula não aparece. É ausência de dado, não de regra. */}
        <ProfitFigure profit={plano.realizable_profit} marginPct={null} />
        <Sub>
          em {dias} dia{dias > 1 ? "s" : ""}
        </Sub>
      </td>

      <td>
        <span className="figure text-note">{formatSilverCompact(plano.units)}</span>
        <Sub>
          {plano.days_to_sell === null ? "escoa ?" : `escoa em ${plano.days_to_sell}d`}
        </Sub>
      </td>

      <td>
        <span
          className={`figure inline-block rounded-sm border px-1.5 py-px text-aux ${trava.tom}`}
          title={trava.dica}
        >
          {trava.texto}
        </span>
      </td>
    </tr>
  );
}
