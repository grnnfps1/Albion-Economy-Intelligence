import { PageShell } from "@/components/PageShell";
import { CopyButton } from "@/components/sheet/CopyButton";
import { ExportButton } from "@/components/sheet/ExportButton";
import {
  EmptyMaterialCell,
  MAX_MATERIAL_COLUMNS,
  MaterialCell,
  MaterialOverflow,
  materialColumnCount,
  materialColumns,
  materialWidth,
} from "@/components/sheet/MaterialCell";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { SpreadWarning, TierBadge } from "@/components/ui/Badges";
import { AgeTag, ProfitFigure } from "@/components/ui/Figures";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchFarming, type FarmPlan,
  ultimaFalha,
} from "@/lib/api";
import { toExportSheet, type ExportColumn } from "@/lib/export";
import { formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";
import { tierBorderLeft } from "@/lib/tiers";

export const dynamic = "force-dynamic";

/**
 * Cultivo e criação consomem poucos insumos: semente ou filhote, e ração.
 *
 * Medido contra a API: dos 67 planos, 21 têm uma entrada e 46 têm duas —
 * nenhum passa de dois. A tabela abre o que as linhas visíveis usam, com o
 * mesmo teto e o mesmo aviso de excedente do craft, para a regra ser uma só.
 */

function colunas(maxEntradas: number): SheetColumn[] {
  const [primeira, ...demais] = materialColumns(maxEntradas, "entrada");
  return [
    { label: "o que plantar ou criar", width: "item", left: true },
    { ...primeira, label: "insumo" },
    ...demais,
    { label: "ciclo", width: "focus", title: "do plantio à colheita" },
    { label: "você gasta", width: "num", title: "insumo mais a ração do período" },
    { label: "lucro/dia", width: "num", title: "o que compara 22 h de fazenda com 28 d de criação" },
    { label: "prata/focus", width: "num" },
    { label: "sai por ciclo", width: "mat", left: true },
    { label: "idade", width: "mini" },
  ];
}

function exportacao(maxEntradas: number): ExportColumn<FarmPlan>[] {
  const entradas: ExportColumn<FarmPlan>[] = [];
  for (let i = 0; i < maxEntradas; i++) {
    entradas.push(
      { header: `entrada ${i + 1} id`, value: (p) => p.inputs[i]?.item ?? null },
      { header: `entrada ${i + 1} papel`, value: (p) => p.inputs[i]?.role ?? null },
      { header: `entrada ${i + 1} qtd`, value: (p) => p.inputs[i]?.quantity ?? null },
      { header: `entrada ${i + 1} unitário`, value: (p) => p.inputs[i]?.unit_price ?? null },
      { header: `entrada ${i + 1} cidade`, value: (p) => p.inputs[i]?.location ?? null },
    );
  }
  return [
    { header: "imagem", value: (p) => p.icon_url, image: true },
    { header: "id", value: (p) => p.item },
    { header: "nome", value: (p) => p.item_name },
    { header: "tier", value: (p) => p.tier },
    { header: "estação", value: (p) => p.station_label },
    { header: "tipo", value: (p) => p.kind },
    ...entradas,
    { header: "ciclo (s)", value: (p) => p.economics.cycle_seconds },
    { header: "você gasta", value: (p) => p.economics.input_cost },
    { header: "preço do npc", value: (p) => p.npc_silver_cost },
    { header: "lucro por ciclo", value: (p) => p.economics.profit_per_cycle },
    { header: "lucro por dia", value: (p) => p.economics.profit_per_day },
    { header: "margem %", value: (p) => p.economics.margin_pct },
    { header: "prata/focus", value: (p) => p.economics.profit_per_focus },
    { header: "focus", value: (p) => p.economics.focus_cost },
    {
      header: "saída principal",
      value: (p) =>
        p.outputs
          .filter((o) => o.primary)
          .map((o) => `${o.item}=${o.amount_min}-${o.amount_max}`)
          .join(" | "),
    },
    { header: "saídas sem preço", value: (p) => p.economics.outputs_without_price.join(", ") },
    { header: "cidades envolvidas", value: (p) => p.material_sourcing.cities_involved },
    { header: "motivo do desconhecido", value: (p) => p.economics.reason },
  ];
}

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

  // Uma coluna por entrada, limitada ao que as linhas visíveis usam: abrir três
  // colunas para uma tabela só de cultivo encheria a tela de traço.
  const maxEntradas = materialColumnCount(
    (data?.plans ?? []).map((p) => p.inputs.length),
  );

  return (
    <PageShell
      titulo="Agricultura"
      descricao="Um ciclo de fazenda leva 22 horas e um filhote de montaria leva quase um mês: comparar “lucro por ciclo” entre os dois não significa nada. Tudo aqui sai em prata por dia e prata por focus."
      contagem={data ? `${data.plans.length} de ${data.total} planos` : undefined}
      grupos={GRUPOS}
      busca={false}
      prefs={prefs}
      acoes={
        <ExportButton
          // A planilha não tem restrição de largura: exporta até o teto real.
          sheet={toExportSheet(data?.plans ?? [], exportacao(MAX_MATERIAL_COLUMNS))}
          screen="agricultura"
          filters={{
            estacao: query.station,
            tipo: query.kind,
            ordem: query.sort_by,
            compra: prefs.buyLocation,
          }}
        />
      }
    >
      {data === null && <ApiDown falha={ultimaFalha()} />}

      {data?.total === 0 && (
        <EmptyState>
          Nenhum plano de agricultura. As tabelas saem do dump: rode{" "}
          <code>python -m app.cli.import_items</code> e depois a coleta, para que semente,
          cultivo e ração tenham preço.
        </EmptyState>
      )}

      {data && data.total > 0 && (
        <SheetTable columns={colunas(maxEntradas)}>
          {data.plans.map((plano) => (
            <FarmLine
              key={`${plano.item}-${plano.kind}`}
              plano={plano}
              maxEntradas={maxEntradas}
            />
          ))}
        </SheetTable>
      )}

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

function FarmLine({
  plano,
  maxEntradas,
}: {
  plano: FarmPlan;
  maxEntradas: number;
}) {
  const eco = plano.economics;
  const positivo = eco.known ? (eco.profit_per_day ?? 0) > 0 : null;
  const principais = plano.outputs.filter((o) => o.primary);
  const estreito = materialWidth(maxEntradas) === "matNarrow";
  const excedentes = plano.inputs.slice(maxEntradas);

  const tinta =
    positivo === true
      ? "bg-[linear-gradient(90deg,rgba(86,192,127,0.08),transparent_32%)]"
      : positivo === false
        ? "bg-[linear-gradient(90deg,rgba(226,85,92,0.08),transparent_32%)]"
        : "";

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
              <TierBadge tier={plano.tier} enchantment={0} />
              <span className="figure rounded-[3px] border border-line bg-raised px-[5px] py-px text-[9.5px] text-muted">
                {plano.station_label}
              </span>
              <span className="figure rounded-[3px] border border-line bg-raised px-[5px] py-px text-[9.5px] text-muted">
                {TIPO_ROTULO[plano.kind] ?? plano.kind.toLowerCase()}
              </span>
            </span>
            <span className="flex min-w-0 items-center">
              <span className="truncate">{plano.item_name ?? plano.item}</span>
              <CopyButton name={plano.item_name} id={plano.item} />
              <MaterialOverflow
                extras={excedentes.length}
                names={excedentes.map((e) => e.item_name ?? e.item)}
              />
            </span>
            <span className="block truncate text-[9px] text-dim">{plano.item}</span>
          </span>
        </span>
      </td>

      {Array.from({ length: maxEntradas }, (_, i) => {
        const entrada = plano.inputs[i];
        if (!entrada) return <EmptyMaterialCell key={`vazio-${i}`} />;
        return (
          <MaterialCell
            key={`${entrada.item}-${entrada.role}`}
            item={entrada.item}
            itemName={entrada.item_name}
            iconUrl={entrada.icon_url}
            quantity={Math.round(entrada.quantity)}
            unitPrice={entrada.unit_price}
            tier={plano.tier}
            locationName={entrada.location}
            isAlternateCity={entrada.is_alternate_city}
            tip={tituloEntrada(entrada, plano.buy_location)}
            compact={estreito}
          />
        );
      })}

      <td className="figure text-[10.5px]">{formatDuracao(eco.cycle_seconds)}</td>

      <td
        title={
          plano.npc_silver_cost === null
            ? undefined
            : `O comerciante de fazenda vende por ${formatSilver(plano.npc_silver_cost)} de prata fixa. O número ao lado usa o preço de mercado — compare os dois antes de decidir.`
        }
      >
        <span className="figure">{formatSilver(eco.input_cost)}</span>
        <span className="lbl mt-px block">
          {plano.npc_silver_cost === null
            ? "insumo + ração"
            : `npc ${formatSilver(plano.npc_silver_cost)}`}
        </span>
        <span className="flex justify-end">
          <SpreadWarning
            cities={plano.material_sourcing.cities_involved}
            savings={plano.material_sourcing.savings}
            savingsPct={plano.material_sourcing.savings_pct}
          />
        </span>
      </td>

      {/* O maior número da linha é o lucro por dia, não o do ciclo: é ele que
          responde "o que colocar na parcela hoje". */}
      <td>
        <ProfitFigure
          profit={eco.profit_per_day}
          marginPct={eco.margin_pct}
          unknownReason={eco.reason}
        />
      </td>

      <td>
        <span
          className={`figure font-semibold text-[13px] ${
            positivo ? "text-up" : positivo === false ? "text-down" : "text-dim"
          }`}
        >
          {eco.profit_per_focus === null ? "—" : formatSilver(eco.profit_per_focus)}
        </span>
        <span className="lbl mt-px block">
          {eco.focus_cost > 0 ? `${formatSilver(eco.focus_cost)} focus` : "sem focus"}
        </span>
      </td>

      <td className="l">
        {principais.map((saida) => (
          <span key={saida.item} className="block truncate" title={saida.item}>
            <span className="figure">
              {saida.amount_min === saida.amount_max
                ? formatSilver(saida.amount_min)
                : `${saida.amount_min}–${saida.amount_max}`}
            </span>
            <span className="ml-1 text-[9.5px] text-dim">{saida.item_name ?? saida.item}</span>
          </span>
        ))}
        {eco.outputs_without_price.length > 0 && (
          <span
            title={`Sem cotação: ${eco.outputs_without_price.join(", ")}. O lucro mostrado está abaixo do real.`}
            className="figure block text-[9px] text-warn"
          >
            ⚠ {eco.outputs_without_price.length} sem preço
          </span>
        )}
      </td>

      <td>
        <AgeTag seconds={plano.inputs[0]?.age_seconds ?? null} />
      </td>
    </tr>
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
