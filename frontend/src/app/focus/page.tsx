import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { CopyButton } from "@/components/sheet/CopyButton";
import { ExportButton } from "@/components/sheet/ExportButton";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { TierBadge } from "@/components/ui/Badges";
import { Figure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchFocus, type FocusPlan } from "@/lib/api";
import { toExportSheet, type ExportColumn } from "@/lib/export";
import { formatSilver } from "@/lib/format";
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
      {data === null && <ApiDown />}

      {data?.total === 0 && (
        <EmptyState>
          Nenhuma operação com focus e dados suficientes.
        </EmptyState>
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
        <p className="max-w-prose p-4 text-[11px] text-dim leading-relaxed">
          Troque a ordenação para “prata/focus” e compare: a taxa mais alta nem sempre é o maior
          ganho, porque o item com melhor taxa costuma ser o que menos gira.
        </p>
      )}
    </PageShell>
  );
}

function FocusLine({ plano, dias }: { plano: FocusPlan; dias: number }) {
  const positivo = (plano.realizable_profit ?? 0) > 0;
  const trava = LIMITADOR[plano.limiter] ?? LIMITADOR.DESCONHECIDO;

  const tinta = positivo
    ? "bg-[linear-gradient(90deg,rgba(86,192,127,0.08),transparent_32%)]"
    : "bg-[linear-gradient(90deg,rgba(226,85,92,0.08),transparent_32%)]";

  return (
    <tr className={tinta}>
      <td className={`l ${tierBorderLeft(plano.tier)}`}>
        <span className="flex min-w-0 items-center gap-2">
          <ItemIcon
            url={plano.icon_url}
            alt={plano.item_name ?? plano.item}
            tier={plano.tier}
            size={22}
          />
          <span className="min-w-0">
            <span className="flex items-center gap-1">
              <TierBadge tier={plano.tier} enchantment={plano.enchantment} />
              <span className="figure rounded-[3px] border border-line bg-raised px-[5px] py-px text-[9.5px] text-muted">
                {plano.route.toLowerCase()}
              </span>
            </span>
            <span className="flex min-w-0 items-center">
              <span className="truncate">{plano.item_name ?? plano.item}</span>
              <CopyButton name={plano.item_name} id={plano.item} />
            </span>
            <span className="block truncate text-[9px] text-dim">{plano.item}</span>
          </span>
        </span>
      </td>

      <td className="figure font-semibold text-[13px]">
        {plano.profit_per_focus === null ? "—" : formatSilver(plano.profit_per_focus)}
      </td>

      <td className="figure text-[10.5px] text-muted">{formatSilver(plano.focus_per_unit)}</td>

      <td>
        <Figure value={plano.units_by_focus} label="unidades" />
      </td>
      <td>
        <Figure value={plano.units_by_liquidity} label={`em ${dias}d`} />
      </td>

      <td>
        <span
          className={`figure font-semibold text-[15px] leading-none ${
            positivo ? "text-up" : "text-down"
          }`}
        >
          {positivo ? "+" : ""}
          {formatSilver(plano.realizable_profit)}
        </span>
        <span className="lbl mt-px block">
          em {dias} dia{dias > 1 ? "s" : ""}
        </span>
      </td>

      <td>
        <span className="figure text-[12px]">{formatSilver(plano.units)}</span>
        <span className="lbl mt-px block">
          {plano.days_to_sell === null ? "escoa ?" : `escoa em ${plano.days_to_sell}d`}
        </span>
      </td>

      <td>
        <span
          className={`figure inline-block rounded-[3px] border px-[6px] py-px text-[10px] ${trava.tom}`}
          title={trava.dica}
        >
          {trava.texto}
        </span>
      </td>
    </tr>
  );
}
