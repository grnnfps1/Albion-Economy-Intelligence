import { ColumnHeader } from "@/components/ColumnHeader";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { CityTag, QualityBadge, TierBadge } from "@/components/ui/Badges";
import { AgeTag, DenseRow, Figure, ProfitFigure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchArbitrage, type Opportunity } from "@/lib/api";
import { formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";

export const dynamic = "force-dynamic";

const COLUNAS = "minmax(13rem,1.4fr) minmax(11rem,1fr) 8.5rem 8.5rem 9rem 8rem 7rem";

const GRUPOS = [
  {
    chave: "strategy", padrao: "IMEDIATA",
    opcoes: [
      { valor: "IMEDIATA", rotulo: "imediata" },
      { valor: "PACIENTE", rotulo: "paciente" },
    ],
  },
  {
    chave: "include_black_market", padrao: "false",
    opcoes: [
      { valor: "false", rotulo: "só cidades" },
      { valor: "true", rotulo: "com black market" },
    ],
  },
];

export default async function ArbitragePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const data = await fetchArbitrage({
    ...feeParams(prefs),
    quantity: String(prefs.quantity),
    min_profit: "1",
    ...query,
    limit: "40",
  });

  return (
    <PageShell
      titulo="Arbitragem"
      descricao={`Comprar numa cidade e vender em outra, com ${formatSilver(prefs.quantity)} unidades. O spread bruto engana: setup fee e imposto comem boa parte, e a estratégia paciente paga o setup duas vezes mesmo se a ordem não executar.`}
      contagem={data ? `${data.opportunities.length} de ${data.total} rotas` : undefined}
      grupos={GRUPOS}
      busca={false}
      prefs={prefs}
    >
      <ColumnHeader
        columns={COLUNAS}
        ordemPadrao="score"
        colunas={[
          { rotulo: "item" },
          { rotulo: "rota" },
          { rotulo: "você gasta", alinhamento: "right" },
          { rotulo: "você recebe", alinhamento: "right" },
          { rotulo: "lucro", alinhamento: "right" },
          { rotulo: "score", alinhamento: "right" },
          { rotulo: "dado", alinhamento: "right" },
        ]}
      />

      {data === null && <ApiDown />}

      {data?.total === 0 && (
        <EmptyState>
          Nenhuma rota viável agora. Pode não haver spread suficiente, ou as cotações estarem
          velhas demais. Não é erro — é o mercado.
        </EmptyState>
      )}

      {data?.opportunities.map((op) => (
        <ArbitrageLine
          key={`${op.item}-${op.origin_slug}-${op.destination_slug}-${op.quality}`}
          op={op}
        />
      ))}
    </PageShell>
  );
}

const BANDA: Record<string, string> = {
  excelente: "border-up/50 text-up",
  muito_boa: "border-up/30 text-up",
  boa: "border-line-strong text-body",
  moderada: "border-warn/40 text-warn",
  ruim: "border-down/40 text-down",
  desconhecida: "border-line text-dim",
};

function ArbitrageLine({ op }: { op: Opportunity }) {
  const eco = op.economics;
  const positivo = eco.known ? (eco.net_profit ?? 0) > 0 : null;

  return (
    <DenseRow tier={op.tier} positive={positivo} columns={COLUNAS}>
      <div className="flex min-w-0 items-center gap-2.5">
        <ItemIcon url={op.icon_url} alt={op.item_name ?? op.item} tier={op.tier} />
        <div className="min-w-0">
          <div className="mb-[3px] flex gap-1">
            <TierBadge tier={op.tier} enchantment={op.enchantment} />
            <QualityBadge quality={op.quality} />
          </div>
          <div className="truncate text-[12.5px] leading-tight" title={op.item}>
            {op.item_name ?? op.item}
          </div>
        </div>
      </div>

      <div className="min-w-0 pr-3">
        <div className="flex items-baseline justify-between gap-2">
          <CityTag city={op.origin} className="text-[11.5px]" />
          <span className="figure text-[11px] text-muted">{formatSilver(op.buy_price)}</span>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <CityTag city={op.destination} className="text-[11.5px]" />
          <span className="figure text-[11px] text-muted">{formatSilver(op.sell_price)}</span>
        </div>
      </div>

      <Figure value={eco.investment} label="investido" />
      <Figure value={eco.gross_revenue} label="antes de taxas" />
      <ProfitFigure profit={eco.net_profit} marginPct={eco.margin_pct} unknownReason={eco.reason} />

      <div className="pr-3 text-right">
        <span
          className={`figure inline-block rounded border px-2 py-[3px] text-[13px] ${
            BANDA[op.score.band] ?? BANDA.desconhecida
          }`}
          title={
            op.score.value === null
              ? `sem dado para: ${op.score.missing.join(", ")}`
              : `confiança ${op.score.confidence}`
          }
        >
          {op.score.value ?? "—"}
        </span>
        <span className="mt-px block text-[9px] text-dim uppercase tracking-[0.05em]">
          {op.score.band.replace("_", " ")}
        </span>
      </div>

      <div className="pr-3 text-right">
        <AgeTag seconds={op.worst_age_seconds} />
        <span className="figure mt-px block text-[9.5px] text-dim">
          {op.liquidity_units_per_day === null
            ? "giro ?"
            : `${formatSilver(op.liquidity_units_per_day)}/dia`}
        </span>
      </div>
    </DenseRow>
  );
}
