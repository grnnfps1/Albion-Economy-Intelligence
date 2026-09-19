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
import { formatDataAge, formatSilver, formatSilverCompact } from "@/lib/format";
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
    // Onde se **produz**, que não é onde se compra: ilha não tem mercado, então
    // quem produz nela compra numa cidade e carrega.
    chave: "produce_on_island",
    padrao: "false",
    opcoes: [
      { valor: "false", rotulo: "na cidade" },
      { valor: "true", rotulo: "na ilha" },
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
/**
 * Os papéis de material, na ordem em que a cadeia os consome.
 *
 * A coluna é do **papel**, não da posição na receita: a ordem do dump não é
 * estável (a variante com token lista o token antes do refinado, a sem token
 * não o lista) e uma coluna que significa coisas diferentes em linhas
 * diferentes não se lê na vertical. Com papel fixo, comparar o preço do pelego
 * de T4 a T8 é correr o olho por uma coluna só.
 *
 * Na variante sem token a coluna do token fica **vazia**. Promover o refinado
 * para ela economizaria uma coluna e destruiria exatamente a propriedade que
 * justifica a mudança.
 */
const PAPEIS = [
  { chave: "bruto", rotulo: "bruto", dica: "o recurso que vem da coleta" },
  { chave: "refinado", rotulo: "refinado", dica: "o refinado do tier anterior" },
  { chave: "token", rotulo: "token", dica: "coração de facção — não retorna" },
  { chave: "outro", rotulo: "outro", dica: "material fora dos três papéis conhecidos" },
] as const;

function papeisPresentes(linhas: CalcRow[]): string[] {
  const vistos = new Set(linhas.flatMap((l) => l.materials.map((m) => m.role)));
  return PAPEIS.filter((p) => vistos.has(p.chave)).map((p) => p.chave);
}

function colunas(papeis: string[]): SheetColumn[] {
  return [
    { label: "tier", width: "focus", left: true },
    { label: "item", width: "item", left: true },
    { label: "você vende por", width: "num", title: "editável — o seu preço vence o coletado" },
    // Uma coluna por papel de material. Empilhá-los dentro da célula do item
    // era o que fazia o terceiro sair do alinhamento e o preço encostar na
    // borda: célula composta não tem largura própria.
    ...papeis.map((chave) => {
      const papel = PAPEIS.find((p) => p.chave === chave);
      return {
        label: papel?.rotulo ?? chave,
        width: "calcMat" as const,
        left: true,
        title: papel?.dica,
      };
    }),
    { label: "material", width: "num", title: "já com o retorno descontado" },
    { label: "taxa da loja", width: "num", title: "item value × 0,1125 × prata por 100 de nutrição ÷ 100" },
    { label: "taxa de venda", width: "num", title: "imposto + setup fee sobre a receita bruta" },
    {
      label: "focus",
      width: "num",
      title:
        "custo em Focus das unidades pedidas, já reduzido pela sua especialização. Fica entre as colunas de custo porque é custo — só não é em prata.",
    },
    { label: "custo de produção", width: "num" },
    { label: "receita bruta", width: "num" },
    { label: "lucro", width: "num" },
    // Investimento em coluna própria: com oito dígitos nos dois, ele brigava com
    // o lucro dentro da mesma célula.
    { label: "investe", width: "num", title: "capital que sai do bolso antes de vender" },
    { label: "margem", width: "pct", title: "sobre a receita bruta; entre parênteses, sobre o custo" },
    { label: "escoa em", width: "mini", title: "quantos dias o giro leva para absorver a quantidade" },
  ];
}

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
  // Base unitária: a tabela mostra **uma** unidade e o filtro de quantidade
  // multiplica. Com o padrão em 100 quase toda coluna nascia com oito dígitos,
  // e as células brigavam entre si antes de qualquer questão de largura.
  const quantidade = query.quantity ?? "1";
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
  const papeis = papeisPresentes(linhas);
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

          <SheetTable columns={colunas(papeis)} freeze={2}>
            {linhas.map((linha) => (
              <Linha
                key={linha.item}
                linha={linha}
                server={data.server}
                buyLocation={data.buy_location}
                sellLocation={data.sell_location}
                papeis={papeis}
              />
            ))}
          </SheetTable>

          <p className="max-w-prose p-4 text-[11px] text-dim leading-relaxed">
            <b>Como ler:</b> a base é <b>uma unidade</b>, e a tabela inteira está multiplicada
            pela quantidade do filtro — agora em {formatSilver(Number(quantidade))}. Tudo que é
            soma escala junto: compra,
            gasto, focus, taxa de venda, custo, receita, lucro e investimento.{" "}
            <b>Margem, prata/focus e a margem sobre o custo não escalam</b>, porque são razões —
            ficam idênticas em 1 e em 10.000 unidades, e se mudassem seria bug.
          </p>
          <p className="max-w-prose px-4 pb-4 text-[11px] text-dim leading-relaxed">
            O <i>comprar N</i> sob o preço de cada material é o consumo total já descontado o
            retorno, arredondado para cima <b>uma vez, no fim</b> — arredondar por unidade e
            multiplicar compraria material a mais. {data.return_note} A <i>taxa da loja</i> é
            por execução, não fixa da sessão: {formatSilver(Number(quantidade))} unidades pagam{" "}
            {formatSilver(Number(quantidade))} vezes. A <i>taxa de venda</i> é imposto mais setup
            fee: uma ordem de venda paga os dois, e o setup mesmo se a ordem não executar. A
            coluna <i>escoa em</i> depende do histórico de mercado; enquanto ele não for
            coletado (<code>python -m app.cli.collect_history</code>) ela diz{" "}
            <i>sem dado</i> — que é diferente de giro zero.
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
      {/* Ao lado da taxa da estação porque é o outro número que só existe na
          tela do jogo: varia por cidade e por dia, e o sistema não tem como
          sabê-lo. Vazio não é "o bônus é zero" — é "não estou modelando", e a
          tira diz isso em vez de calar. */}
      {data.material_return.assumes_no_daily_bonus ? (
        <span className="flex items-center gap-1.5">
          <span className="lbl">bônus do dia</span>
          <span className="text-[10.5px] text-muted">
            assumido zero — informe nas preferências se a cidade tiver bônus hoje
          </span>
        </span>
      ) : (
        <Param
          rotulo="bônus do dia"
          valor={`+${(data.material_return.daily_bonus * 100).toFixed(0)}% em B`}
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
  papeis,
}: {
  linha: CalcRow;
  server: string;
  buyLocation: string;
  sellLocation: string;
  papeis: string[];
}) {
  const positivo = linha.known ? (linha.profit ?? 0) > 0 : null;
  const tinta =
    positivo === true
      ? "bg-[linear-gradient(90deg,rgba(86,192,127,0.08),transparent_32%)]"
      : positivo === false
        ? "bg-[linear-gradient(90deg,rgba(226,85,92,0.08),transparent_32%)]"
        : "";
  // A mesma tinta, como variável, para as colunas presas poderem repintá-la
  // sobre o fundo opaco que o `sticky` exige. Sem isto, prender a identidade
  // apagaria o verde e o vermelho justamente onde eles são mais visíveis.
  const corDaTinta =
    positivo === true
      ? "rgba(86,192,127,0.06)"
      : positivo === false
        ? "rgba(226,85,92,0.06)"
        : "transparent";

  return (
    <tr className={tinta} style={{ "--tinta": corDaTinta } as React.CSSProperties}>
      <td className={`l ${tierBorderLeft(linha.tier)}`}>
        <TierBadge tier={linha.tier} enchantment={linha.enchantment} />
      </td>

      <td className="l">
        <span className="flex min-w-0 items-center gap-2">
          {/* Maior que nas telas de ranking, e de propósito. A densidade cai
              e aqui isso é aceitável: são 27 linhas de uma família, não 40 de
              um ranking — o calculador é para examinar, não para varrer. */}
          <ItemIcon
            url={linha.icon_url}
            alt={linha.item_name ?? linha.item}
            tier={linha.tier}
            size={38}
          />
          <span className="flex min-w-0 items-center">
            <span className="truncate">{linha.item_name ?? linha.item}</span>
            <CopyButton name={linha.item_name} id={linha.item} />
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

      {papeis.map((papel) => {
        const m = linha.materials.find((mat) => mat.role === papel);
        if (!m) {
          // Vazio de propósito: a variante sem token não tem token. Promover o
          // refinado para cá quebraria a leitura vertical da coluna.
          return (
            <td key={papel} className="l text-dim" title={`esta variante não usa ${papel}`}>
              —
            </td>
          );
        }
        return (
          <Material
            key={papel}
            material={m}
            tier={linha.tier}
            server={server}
            buyLocation={buyLocation}
          />
        );
      })}

      <Numero valor={linha.material_cost} dica={
        linha.returned_value === null
          ? undefined
          : `bruto ${formatSilver(linha.material_cost_gross)}, retorno devolve ${formatSilver(linha.returned_value)}`
      } />
      <Numero valor={linha.station_fee} />
      <Numero valor={linha.sale_fee} />

      {/* Focus é custo, e por isso fica junto dos outros custos — só não entra
          no custo de produção, porque não é prata. Prata/focus vem abaixo
          porque é a razão que compara linhas. */}
      <td title="focus das unidades pedidas, já com a sua especialização">
        {linha.focus_cost === 0 ? (
          <span className="text-[10.5px] text-dim">—</span>
        ) : (
          <>
            <span className="figure">{formatSilver(linha.focus_cost)}</span>
            {linha.profit_per_focus !== null && (
              <span className="lbl mt-px block">
                {formatSilver(linha.profit_per_focus)} /focus
              </span>
            )}
          </>
        )}
      </td>

      <Numero valor={linha.production_cost} />
      <Numero valor={linha.gross_revenue} />

      <td title={linha.reason ?? undefined}>
        {linha.profit === null ? (
          <Impedimento linha={linha} />
        ) : (
          <span
            className={`figure font-semibold text-[13px] ${positivo ? "text-up" : "text-down"}`}
          >
            {positivo ? "+" : ""}
            {formatSilver(linha.profit)}
          </span>
        )}
      </td>

      <Numero valor={linha.total_investment} dica="material bruto mais a taxa da estação" />

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

      {/* Traço aqui significava três coisas — sem histórico, giro zero, erro —
          e não distinguia nenhuma. "sem dado" diz a única que é verdade hoje:
          a coleta de histórico não passou por este item. */}
      <td
        className="figure text-[10px] text-dim"
        title={
          linha.days_to_sell === null
            ? "o histórico de mercado deste item ainda não foi coletado — sem ele não dá para estimar o giro"
            : "giro medido no histórico dos últimos 30 dias"
        }
      >
        {linha.days_to_sell === null ? (
          <span className="text-[9.5px]">sem dado</span>
        ) : (
          `${linha.days_to_sell} d`
        )}
      </td>
    </tr>
  );
}

/**
 * Uma coluna de contexto: custo, receita, taxa, investimento.
 *
 * **Abreviada acima de 10.000**, com o valor exato no balão. São os números que
 * situam a decisão, não os que a tomam — e numa produção inteira eles chegam a
 * nove dígitos e estouram a coluna. O lucro não passa por aqui de propósito
 * (ver `formatSilverCompact`).
 */
function Numero({ valor, dica }: { valor: number | null; dica?: string }) {
  if (valor === null) {
    return (
      <td title={dica}>
        <span className="text-[10.5px] text-dim">—</span>
      </td>
    );
  }

  const cheio = formatSilver(valor);
  const curto = formatSilverCompact(valor);
  // O exato sempre alcançável, e sem perder a dica que a coluna já tinha.
  const balao = curto === cheio ? dica : [cheio, dica].filter(Boolean).join(" · ");

  return (
    <td title={balao}>
      <span className="figure">{curto}</span>
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
/**
 * O que impede a linha de ter número.
 *
 * Oito traços numa linha não informam nada — era a queixa, e estava certa. O
 * motivo já vinha na resposta e morava só no `title`, que ninguém descobre.
 *
 * O texto é curto de propósito, e **diferente conforme quem pode resolver**:
 *
 * - falta de **cotação** é da linha e nenhum campo a conserta. É a informação
 *   rara e útil, então vai por extenso: qual material, com nome de gente.
 * - falta de **parâmetro** é global, vale para as 27 linhas e a tira do topo
 *   já a anuncia em âmbar. Repetir a frase inteira vinte e sete vezes seria
 *   ruído (a regra "nada duplicado"), então aqui vai só o ponteiro.
 */
function Impedimento({ linha }: { linha: CalcRow }) {
  const dados = linha.blocked_data;

  if (dados.length > 0) {
    return (
      <span className="flex flex-col items-end gap-px text-[9.5px] text-warn leading-tight">
        {dados.map((falta) => (
          <span key={falta}>{falta}</span>
        ))}
      </span>
    );
  }

  if (linha.blocker === "parametro") {
    return (
      <span className="text-[9.5px] text-warn" title={linha.reason ?? undefined}>
        falta parâmetro ↑
      </span>
    );
  }

  return <span className="text-[10.5px] text-dim">—</span>;
}

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
    <td className="l align-top">
      <HoverTip dica={dica} className="flex w-full items-start gap-1.5">
        <ItemIcon
          url={material.icon_url}
          alt={material.item_name ?? material.item}
          tier={tier}
          size={30}
        />
        <span className="flex min-w-0 flex-1 flex-col items-end gap-px">
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
          {/* "comprar N" ganhou linha própria: espremido ao lado do preço ele
              truncava. A quantidade saiu do badge do ícone pelo mesmo motivo —
              seis dígitos não cabem num selo de 30px. */}
          <span className="flex w-full items-center justify-end gap-px whitespace-nowrap text-[9.5px]">
            <span className="text-muted">comprar {formatSilver(material.buy_units)}</span>
            {/* Nome em português: é o que a busca do mercado no jogo entende,
                e aqui importa mais que em qualquer tela — esta é a lista de
                compras. */}
            <CopyButton name={material.item_name} id={material.item} />
          </span>
        </span>
      </HoverTip>
    </td>
  );
}
