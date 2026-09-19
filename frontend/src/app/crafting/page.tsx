import { PageShell } from "@/components/PageShell";
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
import { CopyButton } from "@/components/sheet/CopyButton";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import {
  CityTag,
  QualityBadge,
  ReturnTag,
  SpreadWarning,
  TierBadge,
  ZoneTag,
} from "@/components/ui/Badges";
import { AgeTag, Figure, RiskProfitFigure } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchCrafting, type CraftOpportunity } from "@/lib/api";
import { toExportSheet, type ExportColumn } from "@/lib/export";
import { formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";
import { tierBorderLeft } from "@/lib/tiers";

export const dynamic = "force-dynamic";

/**
 * Quantas colunas de material a tabela abre — medido, não escolhido.
 *
 * O teto é 7, que é o máximo real do dump (`T7_POTION_ACID@1` usa sete) e o
 * mesmo limite da planilha de referência. O número de colunas efetivamente
 * abertas sai das linhas visíveis: hoje as receitas rastreadas têm no máximo
 * **3** materiais, então a tabela abre 3 e não gasta largura à toa.
 *
 * O cap anterior era 4, arbitrário. Ele não truncava nada hoje — as 375
 * receitas com mais de 3 materiais são comida, poções e shapeshifter, todas
 * `is_tracked = false`, e `/crafting` só lista rastreadas. Era um truncamento
 * **latente**: bastaria alguém acrescentar `food` ou `potions` a
 * `DEFAULT_TRACKED_SUBCATEGORIES` para a tela passar a omitir ingrediente sem
 * avisar.
 */

function colunas(maxMateriais: number): SheetColumn[] {
  return [
    { label: "item", width: "item", left: true },
    ...materialColumns(maxMateriais),
    { label: "você gasta", width: "num", title: "materiais depois do retorno, mais a taxa da estação" },
    { label: "você recebe", width: "num", title: "já descontado o imposto de venda" },
    { label: "lucro ajustado", width: "num" },
    { label: "prata/focus", width: "num", title: "a ordenação principal: focus é o recurso escasso" },
    { label: "focus", width: "focus" },
    { label: "vender em", width: "cidade", left: true },
    { label: "idade", width: "mini" },
    { label: "giro", width: "mini" },
  ];
}

/**
 * O que vai para a planilha: valores crus, não formatados.
 *
 * Os materiais viram pares de colunas (id e preço unitário) em vez de um campo
 * composto: dentro de uma planilha, "2× Madeira T4 @ 58" não soma nem ordena.
 */
function exportacao(maxMateriais: number): ExportColumn<CraftOpportunity>[] {
  const materiais: ExportColumn<CraftOpportunity>[] = [];
  for (let i = 0; i < maxMateriais; i++) {
    materiais.push(
      { header: `mat ${i + 1} id`, value: (o) => o.materials[i]?.item ?? null },
      { header: `mat ${i + 1} nome`, value: (o) => o.materials[i]?.item_name ?? null },
      { header: `mat ${i + 1} qtd`, value: (o) => o.materials[i]?.quantity ?? null },
      { header: `mat ${i + 1} unitário`, value: (o) => o.materials[i]?.unit_price ?? null },
      { header: `mat ${i + 1} cidade`, value: (o) => o.materials[i]?.location ?? null },
    );
  }
  return [
    { header: "imagem", value: (o) => o.icon_url, image: true },
    { header: "id", value: (o) => o.item },
    { header: "nome", value: (o) => o.item_name },
    { header: "tier", value: (o) => o.tier },
    { header: "encanto", value: (o) => o.enchantment },
    { header: "estação", value: (o) => o.station_category },
    ...materiais,
    { header: "você gasta", value: (o) => o.economics.material_cost_net },
    { header: "você recebe", value: (o) => o.economics.sale_revenue_net },
    { header: "taxa da estação", value: (o) => o.economics.station_fee },
    { header: "item value", value: (o) => o.economics.item_value },
    { header: "nutrição", value: (o) => o.economics.nutrition },
    { header: "lucro", value: (o) => o.economics.profit },
    { header: "lucro ajustado ao risco", value: (o) => o.risk.expected_profit },
    { header: "margem %", value: (o) => o.economics.margin_pct },
    { header: "ROI %", value: (o) => o.economics.roi_pct },
    { header: "prata/focus", value: (o) => o.economics.profit_per_focus },
    { header: "focus", value: (o) => o.economics.focus_cost },
    { header: "focus sem spec", value: (o) => o.economics.base_focus_cost },
    { header: "comprar em", value: (o) => o.buy_location },
    { header: "vender em", value: (o) => o.sell_location },
    { header: "zona", value: (o) => o.risk.zone_label },
    { header: "retorno", value: (o) => o.material_return.rate },
    { header: "melhor cidade p/ retorno", value: (o) => o.material_return.best_city_name },
    { header: "giro/dia", value: (o) => o.liquidity_units_per_day },
    { header: "idade venda (s)", value: (o) => o.sell_age_seconds },
    { header: "motivo do desconhecido", value: (o) => o.economics.reason },
  ];
}

const GRUPOS = [
  {
    chave: "sort_by",
    padrao: "profit_per_focus",
    opcoes: [
      { valor: "profit_per_focus", rotulo: "prata/focus" },
      { valor: "profit", rotulo: "lucro" },
      { valor: "roi", rotulo: "ROI" },
    ],
  },
  {
    // Onde comprar cada material. Uma cidade é o padrão porque rota espalhada
    // custa viagem: só vale quando a economia paga o desvio.
    chave: "sourcing_mode",
    padrao: "CIDADE_UNICA",
    opcoes: [
      { valor: "CIDADE_UNICA", rotulo: "uma cidade" },
      { valor: "MAIS_BARATO", rotulo: "mais barato" },
      { valor: "COMPARAR", rotulo: "comparar" },
    ],
  },
  {
    chave: "tier",
    padrao: "",
    opcoes: [
      { valor: "", rotulo: "todos" },
      ...[4, 5, 6, 7, 8].map((t) => ({ valor: String(t), rotulo: `T${t}` })),
    ],
  },
  {
    chave: "station_category",
    padrao: "",
    opcoes: [
      { valor: "", rotulo: "tudo" },
      { valor: "wood", rotulo: "madeira" },
      { valor: "metal", rotulo: "metal" },
      { valor: "leather", rotulo: "couro" },
      { valor: "cloth", rotulo: "tecido" },
    ],
  },
];

export default async function CraftingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const data = await fetchCrafting({
    ...feeParams(prefs),
    buy_location: prefs.buyLocation,
    sell_location: prefs.sellLocation,
    ...query,
    limit: "40",
  });

  const linhas = data?.opportunities ?? [];
  // Uma coluna por material, limitada ao que as linhas visíveis realmente usam.
  const maxMateriais = materialColumnCount(linhas.map((o) => o.materials.length));

  return (
    <PageShell
      titulo="Crafting"
      descricao="Prata por focus manda no ranking: focus é o recurso escasso, e um craft que rende mais gastando três vezes mais focus é o pior negócio dos dois."
      contagem={data ? `${data.opportunities.length} de ${data.total} receitas` : undefined}
      grupos={GRUPOS}
      prefs={prefs}
      acoes={
        <ExportButton
          // A planilha não tem restrição de largura: exporta até o teto real,
          // para que um ingrediente nunca falte no arquivo por caber mal na tela.
          sheet={toExportSheet(linhas, exportacao(MAX_MATERIAL_COLUMNS))}
          screen="crafting"
          filters={{
            tier: query.tier,
            estacao: query.station_category,
            ordem: query.sort_by,
            compra: prefs.buyLocation,
            venda: prefs.sellLocation,
          }}
        />
      }
    >
      {data === null && (
        <ApiDown />
      )}

      {data?.total === 0 && (
        <EmptyState>
          Nenhuma receita com dados suficientes. O custo precisa de cotação de cada material em{" "}
          {prefs.buyLocation}. Rode a coleta ou tente outra cidade nas preferências.
        </EmptyState>
      )}

      {data && data.total > 0 && (
        <SheetTable columns={colunas(maxMateriais)}>
          {linhas.map((op) => (
            <CraftLine
              key={`${op.item}-${op.recipe_variant}`}
              op={op}
              maxMateriais={maxMateriais}
            />
          ))}
        </SheetTable>
      )}

      {data && data.opportunities.length > 0 && (
        <p className="max-w-prose p-4 text-[11px] text-dim leading-relaxed">
          <b>Como ler:</b> <i>você gasta</i> é o custo dos materiais depois do retorno, mais a
          taxa da estação. <i>Você recebe</i> já desconta o imposto de venda. Nos materiais, o
          número é o preço por unidade; o badge no ícone é a quantidade. A faixa à esquerda é o
          tier. Material com moldura âmbar vem de outra cidade — e o aviso de cidades aparece a
          partir da terceira, porque economia espalhada por quatro mercados custa quatro viagens.
          Vender fora da cidade onde se compra cria uma rota, e rota tem zona: qualquer ponta em
          Caerleon ou no Black Market atravessa <b className="text-down">vermelha/preta</b>, onde
          a carga inteira pode não chegar. O Black Market aceita equipamento, nunca recurso.
          A marca <i>↩</i> é o retorno de material: ele muda com a cidade, e craftar na cidade
          com bônus da família devolve 24,8% do material em vez de 15,2%.
        </p>
      )}
    </PageShell>
  );
}

/**
 * Tooltip do material: preço, e o que o desvio de cidade compra.
 *
 * O rótulo diz a consequência, não o nome do campo: "economiza X contra
 * Caerleon" responde a pergunta que "cidade alternativa" só levanta.
 */
function titulo(m: CraftOpportunity["materials"][number], base: string): string {
  const linha = `${m.item_name ?? m.item}: ${m.quantity} × ${formatSilver(m.unit_price)} = ${formatSilver(m.total_price)}`;
  if (!m.is_alternate_city) return linha;
  if (m.savings_vs_base === null) {
    return `${linha} · ${base} não tem cotação deste material; só ${m.location} tem.`;
  }
  return `${linha} · comprando em ${m.location} você economiza ${formatSilver(m.savings_vs_base)} contra ${base}.`;
}

function CraftLine({
  op,
  maxMateriais,
}: {
  op: CraftOpportunity;
  maxMateriais: number;
}) {
  const eco = op.economics;
  const positivo = eco.known ? (eco.profit ?? 0) > 0 : null;
  const estreito = materialWidth(maxMateriais) === "matNarrow";
  // O que não coube. Nunca deve acontecer com o teto em 7, mas se acontecer a
  // linha diz — omitir ingrediente em silêncio é pior que faltar coluna.
  const excedentes = op.materials.slice(maxMateriais);

  // O tingimento de lucro vence o zebrado: ele é informação, o zebrado é só
  // apoio para o olho segurar a horizontal.
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
              <QualityBadge quality={1} />
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
              <MaterialOverflow
                extras={excedentes.length}
                names={excedentes.map((m) => m.item_name ?? m.item)}
              />
            </span>
            <span className="block truncate text-[9px] text-dim">{op.item}</span>
          </span>
        </span>
      </td>

      {Array.from({ length: maxMateriais }, (_, i) => {
        const m = op.materials[i];
        if (!m) return <EmptyMaterialCell key={`vazio-${i}`} />;
        return (
          <MaterialCell
            key={m.item}
            item={m.item}
            itemName={m.item_name}
            iconUrl={m.icon_url}
            quantity={m.quantity}
            unitPrice={m.unit_price}
            tier={op.tier}
            locationName={m.location}
            isAlternateCity={m.is_alternate_city}
            tip={titulo(m, op.buy_location)}
            compact={estreito}
          />
        );
      })}

      <td>
        <Figure value={eco.material_cost_net} label="materiais + taxas" />
        {/* O aviso de espalhamento qualifica justamente este número: ele é o
            custo depois de o material vir de N cidades. */}
        <span className="flex justify-end">
          <SpreadWarning
            cities={op.material_sourcing.cities_involved}
            savings={op.material_sourcing.savings}
            savingsPct={op.material_sourcing.savings_pct}
          />
        </span>
      </td>
      <td>
        <Figure value={eco.sale_revenue_net} label="após imposto" />
      </td>
      <td>
        <RiskProfitFigure
          grossProfit={eco.profit}
          expectedProfit={op.risk.expected_profit}
          lossProbability={op.risk.loss_probability}
          crossesOpenWorld={op.risk.crosses_open_world}
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
      </td>

      <td className="figure text-[10.5px] text-muted">
        {formatSilver(eco.focus_cost)}
        {/* Sem spec informado o custo é o do dump. A tela diz, em vez de
            apresentar o número como se fosse do usuário. */}
        {eco.base_focus_cost !== null && eco.base_focus_cost !== eco.focus_cost && (
          <span className="block text-[9px] text-dim line-through">
            {formatSilver(eco.base_focus_cost)}
          </span>
        )}
      </td>

      <td className="l">
        <CityTag city={op.sell_location} className="text-[10.5px]" />
        <span className="mt-px flex">
          <ZoneTag zone={op.risk.zone} label={op.risk.zone_label} />
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
