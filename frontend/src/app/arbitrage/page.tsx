import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { ComoLer } from "@/components/sheet/ComoLer";
import { Aviso, Param, ParamStrip, ParamsDeTaxa } from "@/components/sheet/Chrome";
import { CopyButton } from "@/components/sheet/CopyButton";
import { SHEET_ICON } from "@/components/sheet/Chrome";
import { ExportButton } from "@/components/sheet/ExportButton";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { CityTag, QualityBadge, TierBadge, ZoneTag } from "@/components/ui/Badges";
import { AgeTag, Figure, RiskProfitFigure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchArbitrage, type Opportunity,
  ultimaFalha,
} from "@/lib/api";
import { toExportSheet, type ExportColumn } from "@/lib/export";
import { formatSilver, formatSilverCompact } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";
import { tierBorderLeft } from "@/lib/tiers";

export const dynamic = "force-dynamic";

/** A rota vira duas colunas — comprar onde, vender onde —, não uma célula. */
const COLUNAS: SheetColumn[] = [
  { label: "item", width: "item", left: true },
  { label: "comprar em", width: "cidade", left: true },
  { label: "vender em", width: "cidade", left: true },
  { label: "você gasta", width: "num", title: "capital imobilizado na compra" },
  { label: "você recebe", width: "num", title: "receita bruta, antes das taxas" },
  { label: "lucro ajustado", width: "num" },
  { label: "score", width: "focus" },
  { label: "idade", width: "mini" },
  { label: "giro", width: "mini" },
];

const EXPORTACAO: ExportColumn<Opportunity>[] = [
  { header: "imagem", value: (o) => o.icon_url, image: true },
  { header: "id", value: (o) => o.item },
  { header: "nome", value: (o) => o.item_name },
  { header: "tier", value: (o) => o.tier },
  { header: "encanto", value: (o) => o.enchantment },
  { header: "qualidade", value: (o) => o.quality },
  { header: "comprar em", value: (o) => o.origin },
  { header: "preço de compra", value: (o) => o.buy_price },
  { header: "vender em", value: (o) => o.destination },
  { header: "preço de venda", value: (o) => o.sell_price },
  { header: "zona", value: (o) => o.risk.zone_label },
  { header: "quantidade", value: (o) => o.economics.quantity },
  { header: "investido", value: (o) => o.economics.investment },
  { header: "receita bruta", value: (o) => o.economics.gross_revenue },
  { header: "taxas", value: (o) => o.economics.fees },
  { header: "lucro", value: (o) => o.economics.net_profit },
  { header: "lucro ajustado ao risco", value: (o) => o.risk.expected_profit },
  { header: "margem %", value: (o) => o.economics.margin_pct },
  { header: "ROI %", value: (o) => o.economics.roi_pct },
  { header: "score", value: (o) => o.score.value },
  { header: "faixa", value: (o) => o.score.band },
  { header: "confiança", value: (o) => o.score.confidence },
  { header: "giro/dia", value: (o) => o.liquidity_units_per_day },
  { header: "idade da ponta mais velha (s)", value: (o) => o.worst_age_seconds },
  { header: "motivo do desconhecido", value: (o) => o.economics.reason },
];

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
      acoes={
        <ExportButton
          sheet={toExportSheet(data?.opportunities ?? [], EXPORTACAO)}
          screen="arbitragem"
          filters={{
            estrategia: query.strategy,
            blackmarket: query.include_black_market,
            quantidade: prefs.quantity,
          }}
        />
      }
    >
      {data === null && <ApiDown falha={ultimaFalha()} />}

      {data?.total === 0 && (
        <EmptyState>
          Nenhuma rota viável agora. Pode não haver spread suficiente, ou as cotações estarem
          velhas demais. Não é erro — é o mercado.
        </EmptyState>
      )}

      {data && !data.fees.complete && (
        <Aviso>
          Falta configurar: {data.fees.missing.join(", ")}. Sem imposto e setup fee a
          plataforma responde <b>desconhecido</b> — arbitragem calculada sem taxa inventa
          lucro em toda linha.
        </Aviso>
      )}

      {data && data.total > 0 && (
        <ParamStrip>
          <Param rotulo="estratégia" valor={data.strategy}
            dica="IMEDIATA consome ordens existentes; PACIENTE cria ordem e paga setup nas duas pernas" />
          <Param rotulo="quantidade" valor={formatSilver(data.quantity)} />
          <ParamsDeTaxa fees={data.fees} />
          <Param rotulo="risco"
            valor={data.risk.modelled
              ? `${(data.risk.loss_pct_blue * 100).toFixed(0)}% / ${(data.risk.loss_pct_red_black * 100).toFixed(0)}%`
              : "não modelado"}
            dica="perda em zona azul / vermelha-preta. Zero significa não estar modelando perda, e o ajustado sai igual ao bruto." />
        </ParamStrip>
      )}

      {data && data.total > 0 && (
        <SheetTable columns={COLUNAS}>
          {data.opportunities.map((op) => (
            <ArbitrageLine
              key={`${op.item}-${op.origin_slug}-${op.destination_slug}-${op.quality}`}
              op={op}
            />
          ))}
        </SheetTable>
      )}

      {data && data.opportunities.length > 0 && (
        <ComoLer>
          <p className="max-w-prose p-4 text-note text-dim leading-relaxed">
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
        </ComoLer>
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

  // O tingimento de lucro vence o zebrado: ele é informação, o zebrado é apoio.
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
          <ItemIcon url={op.icon_url} alt={op.item_name ?? op.item} tier={op.tier} size={SHEET_ICON.linha} />
          <span className="min-w-0">
            <span className="flex items-center gap-1">
              <TierBadge tier={op.tier} enchantment={op.enchantment} />
              <QualityBadge quality={op.quality} />
            </span>
            <span className="flex min-w-0 items-center">
              <span className="truncate">{op.item_name ?? op.item}</span>
              <CopyButton name={op.item_name} id={op.item} />
            </span>
            <span className="block truncate text-micro text-dim">{op.item}</span>
          </span>
        </span>
      </td>

      <td className="l">
        <CityTag city={op.origin} className="text-aux" />
        <span className="figure block text-aux text-muted">{formatSilverCompact(op.buy_price)}</span>
      </td>

      <td className="l">
        <CityTag city={op.destination} className="text-aux" />
        <span className="figure block text-aux text-muted">{formatSilverCompact(op.sell_price)}</span>
        <span className="mt-px flex">
          <ZoneTag zone={op.risk.zone} label={op.risk.zone_label} />
        </span>
      </td>

      <td>
        <Figure value={eco.investment} label="investido" />
      </td>
      <td>
        <Figure value={eco.gross_revenue} label="antes de taxas" />
      </td>
      <td>
        <RiskProfitFigure
          grossProfit={eco.net_profit}
          expectedProfit={op.risk.expected_profit}
          lossProbability={op.risk.loss_probability}
          crossesOpenWorld={op.risk.crosses_open_world}
          marginPct={eco.margin_pct}
          unknownReason={eco.reason}
        />
      </td>

      <td>
        <span
          className={`figure inline-block rounded border px-[6px] py-[2px] text-note ${
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
        <span className="lbl block">{op.score.band.replace("_", " ")}</span>
      </td>

      <td>
        <AgeTag seconds={op.worst_age_seconds} />
      </td>

      <td className="figure text-aux text-dim">
        {op.liquidity_units_per_day === null
          ? "—"
          : `${formatSilver(op.liquidity_units_per_day)}/d`}
      </td>
    </tr>
  );
}
