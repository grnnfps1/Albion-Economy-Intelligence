import { PriceInput } from "@/components/calculator/PriceInput";
import { PageShell } from "@/components/PageShell";
import { CopyButton } from "@/components/sheet/CopyButton";
import { ExportButton } from "@/components/sheet/ExportButton";
import { HoverTip } from "@/components/sheet/HoverTip";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { ReturnTag, TierBadge } from "@/components/ui/Badges";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchCalculator, type CalcMaterial, type CalcRow } from "@/lib/api";
import { toExportSheet, type ExportColumn } from "@/lib/export";
import { formatDataAge, formatSilver } from "@/lib/format";
import { feeParams, getPreferences } from "@/lib/preferences";
import { tierBorderLeft } from "@/lib/tiers";

export const dynamic = "force-dynamic";

const FAMILIAS: [string, string][] = [
  ["LEATHER", "couro"],
  ["CLOTH", "tecido"],
  ["PLANKS", "tábuas"],
  ["METALBAR", "barras"],
  ["STONEBLOCK", "blocos"],
];

const GRUPOS = [
  { chave: "family", padrao: "LEATHER", opcoes: FAMILIAS.map(([v, r]) => ({ valor: v, rotulo: r })) },
  {
    // A coluna da matriz de retorno. **Não** há campo de taxa: o número vem da
    // matriz da fase 14, e o que se escolhe é a situação.
    chave: "use_focus",
    padrao: "false",
    opcoes: [
      { valor: "false", rotulo: "sem focus" },
      { valor: "true", rotulo: "com focus" },
    ],
  },
  {
    chave: "quantity",
    padrao: "100",
    opcoes: [10, 100, 500, 1000].map((q) => ({ valor: String(q), rotulo: String(q) })),
  },
];

/**
 * As colunas, na ordem em que a conta se constrói.
 *
 * A planilha de referência mostra o resultado primeiro e os componentes
 * depois. Aqui é o contrário, de propósito: num **calculador** a ordem que
 * ensina é a da conta — material, taxas, custo, receita, lucro. Quem só quer o
 * resultado lê a última coluna; quem quer entender lê da esquerda.
 */
const COLUNAS: SheetColumn[] = [
  { label: "tier", width: "focus", left: true },
  { label: "item", width: "item", left: true },
  { label: "você vende por", width: "num", title: "editável — o seu preço vence o coletado" },
  { label: "material", width: "num", title: "já com o retorno descontado" },
  { label: "taxa da loja", width: "num", title: "item value × 0,1125 × prata por 100 de nutrição ÷ 100" },
  { label: "taxa de venda", width: "num", title: "imposto + setup fee sobre a receita bruta" },
  { label: "custo de produção", width: "num" },
  { label: "receita bruta", width: "num" },
  { label: "lucro", width: "num" },
  { label: "margem", width: "pct", title: "sobre a receita bruta; entre parênteses, sobre o custo" },
  { label: "escoa em", width: "mini", title: "quantos dias o giro leva para absorver a quantidade" },
];

const EXPORTACAO: ExportColumn<CalcRow>[] = [
  { header: "imagem", value: (r) => r.icon_url, image: true },
  { header: "tier", value: (r) => r.tier_label },
  { header: "id", value: (r) => r.item },
  { header: "nome", value: (r) => r.item_name },
  { header: "preço de venda", value: (r) => r.sell_price },
  { header: "preço editado?", value: (r) => (r.sell_price_is_manual ? "sim" : "não") },
  { header: "material (com retorno)", value: (r) => r.material_cost },
  { header: "material (bruto)", value: (r) => r.material_cost_gross },
  { header: "valor retornado", value: (r) => r.returned_value },
  { header: "taxa da loja", value: (r) => r.station_fee },
  { header: "taxa de venda", value: (r) => r.sale_fee },
  { header: "custo de produção", value: (r) => r.production_cost },
  { header: "receita bruta", value: (r) => r.gross_revenue },
  { header: "lucro", value: (r) => r.profit },
  { header: "margem % (sobre receita)", value: (r) => r.margin_pct },
  { header: "margem % (sobre custo)", value: (r) => r.margin_on_cost_pct },
  { header: "focus", value: (r) => r.focus_cost },
  { header: "prata/focus", value: (r) => r.profit_per_focus },
  { header: "investimento", value: (r) => r.total_investment },
  { header: "dias para escoar", value: (r) => r.days_to_sell },
  { header: "variante usada", value: (r) => r.variant_label },
  { header: "variante descartada", value: (r) => r.alternative_label },
  { header: "motivo do desconhecido", value: (r) => r.reason },
];

export default async function CalculadoraPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const quantidade = query.quantity ?? "100";
  const data = await fetchCalculator({
    ...feeParams(prefs),
    buy_location: prefs.buyLocation,
    sell_location: prefs.sellLocation,
    family: query.family ?? "LEATHER",
    quantity: quantidade,
    use_focus: query.use_focus ?? String(prefs.useFocus),
    ...Object.fromEntries(Object.entries(query).filter(([, v]) => v !== undefined)),
  } as Record<string, string>);

  const linhas = data?.rows ?? [];
  const familia = FAMILIAS.find(([v]) => v === data?.family)?.[1] ?? "";

  return (
    <PageShell
      titulo="Calculador"
      descricao="Uma família por vez, todas as combinações de tier e encantamento. Edite o preço de venda ou de qualquer material e a tabela inteira recalcula. O ranking de /crafting continua respondendo outra pergunta: onde gastar o focus de hoje."
      contagem={data ? `${linhas.length} linhas de ${familia} · ${formatSilver(Number(quantidade))} un` : undefined}
      grupos={GRUPOS}
      busca={false}
      prefs={prefs}
      acoes={
        <ExportButton
          sheet={toExportSheet(linhas, EXPORTACAO)}
          screen="calculadora"
          filters={{ familia: data?.family, quantidade, cidade: prefs.buyLocation }}
        />
      }
    >
      {data === null && <ApiDown />}

      {data && linhas.length === 0 && (
        <EmptyState>
          Nenhum item desta família no catálogo. Rode{" "}
          <code>python -m app.cli.import_items</code>.
        </EmptyState>
      )}

      {data && linhas.length > 0 && (
        <>
          <Parametros data={data} quantidade={Number(quantidade)} />

          <SheetTable columns={COLUNAS}>
            {linhas.map((linha) => (
              <Linha
                key={linha.item}
                linha={linha}
                server={data.server}
                buyLocation={data.buy_location}
                sellLocation={data.sell_location}
              />
            ))}
          </SheetTable>

          <p className="max-w-prose p-4 text-[11px] text-dim leading-relaxed">
            <b>Como ler:</b> o badge no ícone de cada material é <i>quanto comprar</i> para as{" "}
            {formatSilver(Number(quantidade))} unidades — já descontado o retorno e arredondado
            para cima, porque não se compra meio pelego. {data.return_note} A{" "}
            <i>taxa de venda</i> é imposto mais setup fee: uma ordem de venda paga os dois, e o
            setup mesmo se a ordem não executar. A margem aparece sobre a receita bruta e, entre
            parênteses, sobre o custo de produção — a segunda é a definição que a planilha usa.
          </p>
        </>
      )}
    </PageShell>
  );
}

/** Os parâmetros globais, e o que deles é escolha e o que é derivado. */
function Parametros({
  data,
  quantidade,
}: {
  data: NonNullable<Awaited<ReturnType<typeof fetchCalculator>>>;
  quantidade: number;
}) {
  const p = data.params;
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-line border-b px-4 py-2 text-[11px]">
      <Param rotulo="quantidade" valor={formatSilver(quantidade)} />
      {/* A taxa de retorno não é campo: vem da matriz, e o que se escolhe é a
          cidade e o Focus. Campo livre convidaria a digitar errado um número
          que o sistema já sabe. */}
      <span className="flex items-center gap-1.5">
        <span className="lbl">retorno</span>
        <ReturnTag
          rate={data.material_return.rate}
          isBestCity={data.material_return.is_best_city}
          bestCityName={data.material_return.best_city_name}
          delta={data.material_return.delta}
          mappingKnown={data.material_return.mapping_known}
        />
      </span>
      {/* Único parâmetro sem padrão. Vazio é estado legítimo aqui, e a tela
          orienta onde ler o número em vez de inventar um. */}
      {p.station_fee_per_100_nutrition === null ? (
        <span className="flex items-center gap-1.5">
          <span className="lbl">taxa da loja</span>
          <span className="figure rounded-[2px] border border-warn px-1.5 py-px text-[10.5px] text-warn">
            desconhecida
          </span>
          <span className="text-[10.5px] text-muted">
            abra a estação no jogo e leia a taxa de uso — costuma ficar na casa das
            centenas (a planilha de referência usava 184). Informe nas preferências.
          </span>
        </span>
      ) : (
        <Param
          rotulo="taxa da loja"
          valor={`${formatSilver(p.station_fee_per_100_nutrition)} / 100 nutr.`}
        />
      )}
      <Param
        rotulo="imposto"
        valor={p.fees.sales_tax_pct === null ? "—" : `${(p.fees.sales_tax_pct * 100).toFixed(1)}%`}
      />
      <Param
        rotulo="setup fee"
        valor={p.fees.setup_fee_pct === null ? "—" : `${(p.fees.setup_fee_pct * 100).toFixed(1)}%`}
      />
      {!p.complete && (
        <span className="text-[10.5px] text-warn">
          falta configurar: {p.missing.join(", ")}
        </span>
      )}
    </div>
  );
}

function Param({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="lbl">{rotulo}</span>
      <span className="figure text-body">{valor}</span>
    </span>
  );
}

function Linha({
  linha,
  server,
  buyLocation,
  sellLocation,
}: {
  linha: CalcRow;
  server: string;
  buyLocation: string;
  sellLocation: string;
}) {
  const positivo = linha.known ? (linha.profit ?? 0) > 0 : null;
  const tinta =
    positivo === true
      ? "bg-[linear-gradient(90deg,rgba(86,192,127,0.08),transparent_32%)]"
      : positivo === false
        ? "bg-[linear-gradient(90deg,rgba(226,85,92,0.08),transparent_32%)]"
        : "";

  return (
    <tr className={tinta}>
      <td className={`l ${tierBorderLeft(linha.tier)}`}>
        <TierBadge tier={linha.tier} enchantment={linha.enchantment} />
      </td>

      <td className="l">
        <span className="flex min-w-0 items-center gap-2">
          <ItemIcon
            url={linha.icon_url}
            alt={linha.item_name ?? linha.item}
            tier={linha.tier}
            size={22}
          />
          <span className="min-w-0">
            <span className="flex min-w-0 items-center">
              <span className="truncate">{linha.item_name ?? linha.item}</span>
              <CopyButton name={linha.item_name} id={linha.item} />
            </span>
            {/* Os materiais ficam aqui, com o badge dizendo quanto comprar.
                Não repetimos a receita em texto: as colunas de material já
                são a receita, e repetir gasta a largura das de decisão. */}
            <span className="mt-px flex items-center gap-1.5">
              {linha.materials.map((m) => (
                <Material
                  key={m.item}
                  material={m}
                  tier={linha.tier}
                  server={server}
                  buyLocation={buyLocation}
                />
              ))}
            </span>
          </span>
        </span>
      </td>

      <td>
        <PriceInput
          server={server}
          location={sellLocation}
          item={linha.item}
          kind="VENDA"
          value={linha.sell_price}
          collected={linha.sell_collected_price}
          isManual={linha.sell_price_is_manual}
          ageSeconds={linha.sell_age_seconds}
        />
      </td>

      <Numero valor={linha.material_cost} dica={
        linha.returned_value === null
          ? undefined
          : `bruto ${formatSilver(linha.material_cost_gross)}, retorno devolve ${formatSilver(linha.returned_value)}`
      } />
      <Numero valor={linha.station_fee} />
      <Numero valor={linha.sale_fee} />
      <Numero valor={linha.production_cost} />
      <Numero valor={linha.gross_revenue} />

      <td title={linha.reason ?? undefined}>
        {linha.profit === null ? (
          <span className="text-[10.5px] text-dim">—</span>
        ) : (
          <>
            <span
              className={`figure font-semibold text-[13px] ${positivo ? "text-up" : "text-down"}`}
            >
              {positivo ? "+" : ""}
              {formatSilver(linha.profit)}
            </span>
            {linha.total_investment !== null && (
              <span className="lbl mt-px block">
                investe {formatSilver(linha.total_investment)}
              </span>
            )}
          </>
        )}
      </td>

      <td
        className={`figure ${
          positivo ? "text-up" : positivo === false ? "text-down" : "text-dim"
        }`}
      >
        {linha.margin_pct === null ? "—" : `${linha.margin_pct.toFixed(1)}%`}
        {linha.margin_on_cost_pct !== null && (
          <span className="block text-[9px] text-dim">
            ({linha.margin_on_cost_pct.toFixed(1)}%)
          </span>
        )}
      </td>

      <td className="figure text-[10px] text-dim" title="giro medido no histórico">
        {linha.days_to_sell === null ? "—" : `${linha.days_to_sell} d`}
      </td>
    </tr>
  );
}

function Numero({ valor, dica }: { valor: number | null; dica?: string }) {
  return (
    <td title={dica}>
      {valor === null ? (
        <span className="text-[10.5px] text-dim">—</span>
      ) : (
        <span className="figure">{formatSilver(valor)}</span>
      )}
    </td>
  );
}

/**
 * Um material: ícone com a **quantidade a comprar** no badge, e o preço
 * editável no balão de hover.
 *
 * A quantidade do badge é a da lista de compras — já com o retorno e
 * arredondada para cima —, não a da receita. É a diferença entre "a receita
 * pede 5" e "compre 317".
 */
function Material({
  material,
  tier,
  server,
  buyLocation,
}: {
  material: CalcMaterial;
  tier: number | null;
  server: string;
  buyLocation: string;
}) {
  const dica = [
    `${material.item_name ?? material.item} · ${material.item}`,
    `receita pede ${material.quantity} por unidade`,
    `comprar ${formatSilver(material.buy_units)}${
      material.saved_by_return > 0
        ? ` (o retorno poupou ${formatSilver(material.saved_by_return)})`
        : ""
    }`,
    material.location ? `em ${material.location}` : null,
    material.age_seconds !== null ? `cotação ${formatDataAge(material.age_seconds)}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <HoverTip dica={dica} className="flex items-center gap-1">
      <ItemIcon
        url={material.icon_url}
        alt={material.item_name ?? material.item}
        tier={tier}
        quantity={material.buy_units}
        size={18}
      />
      <PriceInput
        server={server}
        location={material.location ?? buyLocation}
        item={material.item}
        kind="COMPRA"
        value={material.unit_price}
        collected={material.collected_price}
        isManual={material.price_is_manual}
        ageSeconds={material.age_seconds}
      />
    </HoverTip>
  );
}
