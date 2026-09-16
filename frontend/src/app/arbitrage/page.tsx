import { ColumnHeader } from "@/components/ColumnHeader";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { CityTag, QualityBadge, TierBadge, ZoneTag } from "@/components/ui/Badges";
import { AgeTag, DenseRow, Figure, RiskProfitFigure } from "@/components/ui/Figures";
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
    // Validado em 16/09/2026 (docs/02-aodp.md): ele preenche buy_price_max em
    // 40/40 equipamentos, com orientação normal. Entra ligado, como destino.
    chave: "include_black_market", padrao: "true",
    opcoes: [
      { valor: "true", rotulo: "com black market" },
      { valor: "false", rotulo: "só cidades" },
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
          { rotulo: "lucro ajustado ao risco", alinhamento: "right" },
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

      {data && data.opportunities.length > 0 && (
        <p className="max-w-prose p-4 text-[11px] text-dim leading-relaxed">
          <b>Zona da rota.</b> Cidade real para cidade real é <i>zona azul</i>. Qualquer ponta em
          Caerleon ou no Black Market atravessa <b className="text-down">vermelha/preta</b> — e
          é por isso que essas rotas pagam mais: o spread maior é o preço do risco de perder a
          carga inteira, não uma vantagem escondida.{" "}
          {data.risk.modelled ? (
            <>
              Com {(data.risk.loss_pct_red_black * 100).toFixed(1)}% de perda em zona aberta e{" "}
              {(data.risk.loss_pct_blue * 100).toFixed(1)}% em azul, o lucro exibido já é o
              esperado: <i>lucro × (1 − p) − investimento × p</i>. O bruto fica riscado ao lado,
              para o desconto continuar auditável.
            </>
          ) : (
            <>
              Você ainda não informou perda esperada, então o lucro exibido é o bruto. Preencha{" "}
              <i>perda %</i> nas preferências para ver o ajustado — perder a carga não custa o
              lucro, custa o lucro <b>e</b> o investimento.
            </>
          )}
        </p>
      )}
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
        <div className="mt-[3px]">
          <ZoneTag zone={op.risk.zone} label={op.risk.zone_label} />
        </div>
      </div>

      <Figure value={eco.investment} label="investido" />
      <Figure value={eco.gross_revenue} label="antes de taxas" />
      <RiskProfitFigure
        grossProfit={eco.net_profit}
        expectedProfit={op.risk.expected_profit}
        lossProbability={op.risk.loss_probability}
        crossesOpenWorld={op.risk.crosses_open_world}
        marginPct={eco.margin_pct}
        unknownReason={eco.reason}
      />

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
