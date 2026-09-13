import { ColumnHeader } from "@/components/ColumnHeader";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { TierBadge } from "@/components/ui/Badges";
import { DenseRow, Figure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchFocus, type FocusPlan } from "@/lib/api";
import { formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";

export const dynamic = "force-dynamic";

const COLUNAS = "minmax(12rem,1.3fr) 8rem 8rem 8rem 9.5rem 9rem 7rem";

const GRUPOS = [
  {
    chave: "sort_by", padrao: "realizable_profit",
    opcoes: [
      { valor: "realizable_profit", rotulo: "ganho realizável" },
      { valor: "profit_per_focus", rotulo: "prata/focus" },
    ],
  },
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
    >
      <ColumnHeader
        columns={COLUNAS}
        ordemPadrao="realizable_profit"
        colunas={[
          { rotulo: "item" },
          { rotulo: "prata / focus", ordenavel: "profit_per_focus", alinhamento: "right" },
          { rotulo: "cabe no focus", alinhamento: "right" },
          { rotulo: "mercado escoa", alinhamento: "right" },
          { rotulo: "ganho realizável", ordenavel: "realizable_profit", alinhamento: "right" },
          { rotulo: "quanto fazer", alinhamento: "right" },
          { rotulo: "trava", alinhamento: "right" },
        ]}
      />

      {data === null && <ApiDown />}

      {data?.total === 0 && (
        <EmptyState>
          Nenhuma operação com focus e dados suficientes.
        </EmptyState>
      )}

      {data?.plans.map((plano) => <FocusLine key={plano.item} plano={plano} dias={data.horizon_days} />)}

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

  return (
    <DenseRow tier={plano.tier} positive={positivo} columns={COLUNAS}>
      <div className="flex min-w-0 items-center gap-2.5">
        <ItemIcon url={plano.icon_url} alt={plano.item_name ?? plano.item} tier={plano.tier} />
        <div className="min-w-0">
          <div className="mb-[3px] flex gap-1">
            <TierBadge tier={plano.tier} enchantment={plano.enchantment} />
            <span className="figure rounded-[3px] border border-line bg-raised px-[5px] py-px text-[9.5px] text-muted">
              {plano.route.toLowerCase()}
            </span>
          </div>
          <div className="truncate text-[12.5px] leading-tight" title={plano.item}>
            {plano.item_name ?? plano.item}
          </div>
        </div>
      </div>

      <div className="pr-3 text-right">
        <span className="figure font-semibold text-[13.5px]">
          {plano.profit_per_focus === null ? "—" : formatSilver(plano.profit_per_focus)}
        </span>
        <span className="mt-px block text-[9px] text-dim uppercase tracking-[0.05em]">
          {formatSilver(plano.focus_per_unit)} focus/un
        </span>
      </div>

      <Figure value={plano.units_by_focus} label="unidades" />
      <Figure value={plano.units_by_liquidity} label={`em ${dias}d`} />

      <div className="pr-3 text-right">
        <div className={`figure font-semibold text-[15px] leading-none ${positivo ? "text-up" : "text-down"}`}>
          {positivo ? "+" : ""}
          {formatSilver(plano.realizable_profit)}
        </div>
        <span className="mt-px block text-[9px] text-dim uppercase tracking-[0.05em]">
          em {dias} dia{dias > 1 ? "s" : ""}
        </span>
      </div>

      <div className="pr-3 text-right">
        <span className="figure text-[12.5px]">{formatSilver(plano.units)}</span>
        <span className="mt-px block text-[9px] text-dim uppercase tracking-[0.05em]">
          {plano.days_to_sell === null ? "escoa ?" : `escoa em ${plano.days_to_sell}d`}
        </span>
      </div>

      <div className="pr-3 text-right">
        <span
          className={`figure inline-block rounded-[3px] border px-[6px] py-px text-[10px] ${trava.tom}`}
          title={trava.dica}
        >
          {trava.texto}
        </span>
      </div>
    </DenseRow>
  );
}
