import { ColumnHeader } from "@/components/ColumnHeader";
import { PageShell } from "@/components/PageShell";
import { CityTag, SpreadWarning, TierBadge } from "@/components/ui/Badges";
import { AgeTag, DenseRow, ProfitFigure } from "@/components/ui/Figures";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchFarming, type FarmPlan } from "@/lib/api";
import { formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";

export const dynamic = "force-dynamic";

const COLUNAS =
  "minmax(13rem,1.5fr) 6.5rem 8rem 8.5rem 7.5rem minmax(13rem,1.6fr) 8rem";

const GRUPOS = [
  {
    // Prata por dia é o padrão porque é o que compara 22 horas de fazenda com
    // 28 dias de criação. Por ciclo, o mais lento ganharia por ser lento.
    chave: "sort_by",
    padrao: "profit_per_day",
    opcoes: [
      { valor: "profit_per_day", rotulo: "prata/dia" },
      { valor: "profit_per_focus", rotulo: "prata/focus" },
      { valor: "profit_per_cycle", rotulo: "por ciclo" },
    ],
  },
  {
    chave: "station",
    padrao: "",
    opcoes: [
      { valor: "", rotulo: "tudo" },
      { valor: "farm", rotulo: "fazenda" },
      { valor: "herbgarden", rotulo: "horta" },
      { valor: "pasture", rotulo: "pasto" },
      { valor: "kennel", rotulo: "canil" },
    ],
  },
  {
    chave: "kind",
    padrao: "",
    opcoes: [
      { valor: "", rotulo: "todos" },
      { valor: "CULTIVO", rotulo: "cultivo" },
      { valor: "CRIACAO", rotulo: "criação" },
      { valor: "PRODUTO", rotulo: "produto" },
    ],
  },
  {
    chave: "sourcing_mode",
    padrao: "CIDADE_UNICA",
    opcoes: [
      { valor: "CIDADE_UNICA", rotulo: "uma cidade" },
      { valor: "MAIS_BARATO", rotulo: "mais barato" },
    ],
  },
];

/** `79200` vira `22 h`; `2404800` vira `27,8 d`. O número cru não diz nada. */
function formatDuracao(segundos: number): string {
  if (segundos <= 0) return "—";
  const horas = segundos / 3600;
  if (horas < 48) return `${horas.toFixed(horas % 1 === 0 ? 0 : 1)} h`;
  return `${(horas / 24).toFixed(1).replace(".", ",")} d`;
}

const TIPO_ROTULO: Record<string, string> = {
  CULTIVO: "cultivo",
  CRIACAO: "criação",
  PRODUTO: "produto",
};

export default async function FarmingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const data = await fetchFarming({
    ...feeParams(prefs),
    buy_location: prefs.buyLocation,
    sell_location: prefs.sellLocation,
    ...query,
    limit: "60",
  });

  return (
    <PageShell
      titulo="Agricultura"
      descricao="Um ciclo de fazenda leva 22 horas e um filhote de montaria leva quase um mês: comparar “lucro por ciclo” entre os dois não significa nada. Tudo aqui sai em prata por dia e prata por focus."
      contagem={data ? `${data.plans.length} de ${data.total} planos` : undefined}
      grupos={GRUPOS}
      busca={false}
      prefs={prefs}
    >
      <ColumnHeader
        columns={COLUNAS}
        ordemPadrao="profit_per_day"
        colunas={[
          { rotulo: "o que plantar ou criar" },
          { rotulo: "ciclo", alinhamento: "right" },
          { rotulo: "você gasta", alinhamento: "right" },
          { rotulo: "lucro / dia", ordenavel: "profit_per_day", alinhamento: "right" },
          { rotulo: "prata / focus", ordenavel: "profit_per_focus", alinhamento: "right" },
          { rotulo: "entra · onde comprar" },
          { rotulo: "sai por ciclo", alinhamento: "right" },
        ]}
      />

      {data === null && <ApiDown />}

      {data?.total === 0 && (
        <EmptyState>
          Nenhum plano de agricultura. As tabelas saem do dump: rode{" "}
          <code>python -m app.cli.import_items</code> e depois a coleta, para que semente,
          cultivo e ração tenham preço.
        </EmptyState>
      )}

      {data?.plans.map((plano) => (
        <FarmLine key={`${plano.item}-${plano.kind}`} plano={plano} />
      ))}

      {data && data.plans.length > 0 && (
        <div className="max-w-prose space-y-2 p-4 text-[11px] text-dim leading-relaxed">
          <p>
            <b>Como ler:</b> <i>ciclo</i> é quanto tempo o plano leva do começo ao fim — é o
            que divide o lucro para virar prata por dia. <i>Você gasta</i> é semente ou filhote
            mais a ração consumida no período. A colheita vem em faixa no dump (3 a 6 por pé); o
            número usa a média dela.
          </p>
          <p>
            <b>O que não foi medido no jogo</b> está separado de propósito — um número
            plausível ao lado de um medido, sem etiqueta, vira medido:
          </p>
          <ul className="list-disc space-y-1 pl-4">
            {data.params.assumptions.map((linha) => (
              <li key={linha}>{linha}</li>
            ))}
          </ul>
        </div>
      )}
    </PageShell>
  );
}

function FarmLine({ plano }: { plano: FarmPlan }) {
  const eco = plano.economics;
  const positivo = eco.known ? (eco.profit_per_day ?? 0) > 0 : null;
  const principais = plano.outputs.filter((o) => o.primary);

  return (
    <DenseRow tier={plano.tier} positive={positivo} columns={COLUNAS}>
      <div className="flex min-w-0 items-center gap-2.5">
        <ItemIcon url={plano.icon_url} alt={plano.item_name ?? plano.item} tier={plano.tier} />
        <div className="min-w-0">
          <div className="mb-[3px] flex gap-1">
            <TierBadge tier={plano.tier} enchantment={0} />
            <span className="figure rounded-[3px] border border-line bg-raised px-[5px] py-px text-[9.5px] text-muted">
              {plano.station_label}
            </span>
            <span className="figure rounded-[3px] border border-line bg-raised px-[5px] py-px text-[9.5px] text-muted">
              {TIPO_ROTULO[plano.kind] ?? plano.kind.toLowerCase()}
            </span>
          </div>
          <div className="truncate text-[12.5px] leading-tight" title={plano.item}>
            {plano.item_name ?? plano.item}
          </div>
        </div>
      </div>

      <div className="pr-3 text-right">
        <span className="figure text-val">{formatDuracao(eco.cycle_seconds)}</span>
        <span className="lbl mt-px block">até colher</span>
      </div>

      <div
        className="pr-3 text-right"
        title={
          plano.npc_silver_cost === null
            ? undefined
            : `O comerciante de fazenda vende por ${formatSilver(plano.npc_silver_cost)} de prata fixa. O número ao lado usa o preço de mercado — compare os dois antes de decidir.`
        }
      >
        <span className="figure text-val">{formatSilver(eco.input_cost)}</span>
        <span className="lbl mt-px block">
          insumo + ração
          {plano.npc_silver_cost !== null && (
            <span className="ml-1 text-dim">· npc {formatSilver(plano.npc_silver_cost)}</span>
          )}
        </span>
      </div>

      {/* O maior número da linha é o lucro por dia, não o do ciclo: é ele que
          responde "o que colocar na parcela hoje". */}
      <ProfitFigure
        profit={eco.profit_per_day}
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
          {eco.focus_cost > 0 ? `${formatSilver(eco.focus_cost)} focus` : "sem focus"}
        </span>
      </div>

      <div className="flex items-center gap-1.5 overflow-hidden">
        {plano.inputs.length === 0 ? (
          <span className="text-[11px] text-dim">nada a comprar</span>
        ) : (
          plano.inputs.map((entrada) => (
            <span
              key={`${entrada.item}-${entrada.role}`}
              title={tituloEntrada(entrada, plano.buy_location)}
              className={`flex shrink-0 items-center gap-1.5 rounded border bg-raised px-1.5 py-[3px] ${
                entrada.is_alternate_city ? "border-warn/40" : "border-line"
              }`}
            >
              <ItemIcon
                url={entrada.icon_url}
                alt={entrada.item}
                tier={plano.tier}
                quantity={Math.round(entrada.quantity)}
                size={28}
              />
              <span className="flex flex-col leading-[1.15]">
                <span className="figure text-[11px]">
                  {formatSilver(entrada.unit_price)}
                  <span className="ml-px text-[9px] text-dim">/un</span>
                </span>
                <CityTag
                  city={entrada.location ?? "—"}
                  alternate={entrada.is_alternate_city}
                  className="text-[9.5px] text-muted"
                />
              </span>
            </span>
          ))
        )}
        <SpreadWarning
          cities={plano.material_sourcing.cities_involved}
          savings={plano.material_sourcing.savings}
          savingsPct={plano.material_sourcing.savings_pct}
        />
      </div>

      <div className="pr-3 text-right">
        {principais.map((saida) => (
          <div key={saida.item} className="truncate" title={saida.item}>
            <span className="figure text-[11.5px]">
              {saida.amount_min === saida.amount_max
                ? formatSilver(saida.amount_min)
                : `${saida.amount_min}–${saida.amount_max}`}
              <span className="ml-1 text-[9.5px] text-dim">
                {saida.item_name ?? saida.item}
              </span>
            </span>
          </div>
        ))}
        <div className="mt-px flex justify-end gap-1.5">
          <AgeTag seconds={plano.inputs[0]?.age_seconds ?? null} />
          {eco.outputs_without_price.length > 0 && (
            <span
              title={`Sem cotação: ${eco.outputs_without_price.join(", ")}. O lucro mostrado está abaixo do real.`}
              className="figure text-[9.5px] text-warn"
            >
              ⚠ {eco.outputs_without_price.length} sem preço
            </span>
          )}
        </div>
      </div>
    </DenseRow>
  );
}

function tituloEntrada(entrada: FarmPlan["inputs"][number], base: string): string {
  const linha = `${entrada.item_name ?? entrada.item} (${entrada.role}): ${entrada.quantity.toLocaleString("pt-BR")} × ${formatSilver(entrada.unit_price)} = ${formatSilver(entrada.total_price)}`;
  if (!entrada.is_alternate_city) return linha;
  if (entrada.savings_vs_base === null) {
    return `${linha} · ${base} não tem cotação deste insumo; só ${entrada.location} tem.`;
  }
  return `${linha} · comprando em ${entrada.location} você economiza ${formatSilver(entrada.savings_vs_base)} contra ${base}.`;
}
