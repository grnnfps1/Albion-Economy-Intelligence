import { PriceInput } from "@/components/calculator/PriceInput";
import { PageShell } from "@/components/PageShell";
import type { CampoPref } from "@/components/PreferencesForm";
import { RetornoPainel } from "@/components/calculator/RetornoPainel";
import { StationFeePrompt } from "@/components/calculator/StationFeePrompt";
import { Param, ParamStrip, ParamsDeTaxa } from "@/components/sheet/Chrome";
import { CampoDeQuantidade } from "@/components/sheet/CampoDeQuantidade";
import { ComoLer } from "@/components/sheet/ComoLer";
import { SHEET_ICON } from "@/components/sheet/Chrome";
import { CopyButton } from "@/components/sheet/CopyButton";
import { ExportButton } from "@/components/sheet/ExportButton";
import { HoverTip } from "@/components/sheet/HoverTip";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { ReturnTag, TierBadge } from "@/components/ui/Badges";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { ItemIcon } from "@/components/ui/ItemIcon";
import {
  fetchCalculator,
  type CalcMaterial,
  type CalcRow,
  type PriceRange,
  ultimaFalha,
} from "@/lib/api";
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

/**
 * Os filtros, com o padrão vindo do que o backend **de fato usou**.
 *
 * ## O defeito que isto conserta
 *
 * Os padrões eram literais (`padrao: "false"`), e a pílula acesa saía de
 * `params.get(chave) ?? padrao`. Só que o valor enviado ao backend não vem só
 * da URL: sem parâmetro na URL, ele vem do **cookie de preferências**. Com
 * "Focus ligado: sim" salvo lá, a conta usava Focus, a decomposição somava os
 * 59% corretamente — e a pílula dizia "sem focus".
 *
 * Nada estava errado no cálculo. Errado estava a tela **afirmando um valor que
 * não era o dela**: a pílula exibia um padrão que ela inventou, sobre um
 * parâmetro cuja fonte é outra.
 *
 * A correção é de princípio, não de sintoma: **o filtro espelha a resposta**.
 * `data.material_return.use_focus` é o que o motor usou; `data.params.quantity`
 * é a quantidade que ele multiplicou. Assim a pílula não tem como mentir, nem
 * quando alguém acrescentar uma terceira fonte de valor.
 */
function grupos(data: Awaited<ReturnType<typeof fetchCalculator>>) {
  const usouFoco = data?.material_return.use_focus ?? false;
  const naIlha = data?.material_return.is_island ?? false;

  return [
    {
      chave: "family",
      padrao: data?.family ?? "LEATHER",
      opcoes: FAMILIAS.map(([v, r]) => ({ valor: v, rotulo: r })),
    },
    {
      // A coluna da matriz de retorno. **Não** há campo de taxa: o número vem
      // da fórmula da fase 20, e o que se escolhe é a situação.
      chave: "use_focus",
      padrao: String(usouFoco),
      opcoes: [
        { valor: "false", rotulo: "sem focus" },
        { valor: "true", rotulo: "com focus" },
      ],
    },
    {
      // Onde se **produz**, que não é onde se compra: ilha não tem mercado,
      // então quem produz nela compra numa cidade e carrega.
      chave: "produce_on_island",
      padrao: String(naIlha),
      opcoes: [
        { valor: "false", rotulo: "na cidade" },
        { valor: "true", rotulo: "na ilha" },
      ],
    },
  ];
}

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

/**
 * As colunas, na ordem em que a conta se constrói.
 *
 * A planilha de referência mostra o resultado primeiro e os componentes
 * depois. Aqui é o contrário, de propósito: num **calculador** a ordem que
 * ensina é a da conta — material, taxas, custo, receita, lucro. Quem só quer o
 * resultado lê a última coluna; quem quer entender lê da esquerda.
 */
function colunas(papeis: string[]): SheetColumn[] {
  return [
    { label: "tier", width: "focus", left: true, sortKey: "tier",
      title: "ordena pelo par (tier, encantamento): T5.4 vem antes de T6.0" },
    { label: "item", width: "item", left: true },
    { label: "vende por", width: "num", title: "você vende por — editável, e o seu preço vence o coletado" },
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
    { label: "taxa loja", width: "num", title: "taxa da loja: item value × 0,1125 × prata por 100 de nutrição ÷ 100" },
    { label: "taxa venda", width: "num", title: "taxa de venda: imposto + setup fee sobre a receita bruta" },
    {
      label: "focus",
      width: "num",
      title:
        "custo em Focus das unidades pedidas, já reduzido pela sua especialização. Fica entre as colunas de custo porque é custo — só não é em prata.",
    },
    // Rótulo curto porque a coluna tem 6,8rem: "custo de produção" não cabia
    // e o navegador cortava no meio da palavra, que é pior que abreviar.
    { label: "custo", width: "num", sortKey: "production_cost",
      title: "custo de produção: material líquido + taxa da loja + taxa de venda" },
    { label: "receita", width: "num", title: "receita bruta, antes das taxas" },
    // A única coluna que não pode truncar, e por isso tem largura própria.
    { label: "lucro", width: "numWide", sortKey: "profit" },
    // Investimento em coluna própria: com oito dígitos nos dois, ele brigava com
    // o lucro dentro da mesma célula.
    { label: "investe", width: "num", sortKey: "total_investment",
      title: "capital que sai do bolso antes de vender" },
    { label: "margem", width: "pct", title: "sobre a receita bruta; entre parênteses, sobre o custo" },
    { label: "escoa em", width: "mini", title: "quantos dias o giro leva para absorver a quantidade" },
  ];
}

/**
 * As preferências que **este** calculador usa, auditadas contra
 * `build_calculator`.
 *
 * Fora ficaram quatro, e cada uma por um motivo conferido no código:
 *
 * | Fora | Por quê |
 * |---|---|
 * | risco de rota (duas) | `build_calculator` não recebe. Refinar numa cidade não envolve viagem; o risco é de `/arbitrage`, onde a rota **é** a operação. |
 * | Focus disponível | Não é parâmetro da rota. O orçamento limita o ranking de `/focus`, não a tabela de uma família. |
 * | Focus por dia | Chega a `_linha` e morre lá: nenhuma coluna o usa. |
 * | Quantidade | Virou pílula de filtro; o campo do painel não é lido por esta tela. |
 *
 * `Spec por item` fica, e o rótulo perdeu o "craft de equipamento": o mecanismo
 * é genérico e um nível informado para `T8_LEATHER` **altera** o custo em Focus
 * desta tabela.
 */
/**
 * A ordenação de abertura, e para onde o terceiro clique volta.
 *
 * Tier crescente não é "nenhuma ordenação": é a coluna que dá sentido ao
 * formato, porque é ela que permite comparar T5.2 com T6.2 correndo o olho na
 * vertical. Por isso ela é uma coluna ordenável como as outras — e ainda assim
 * o destino do terceiro clique.
 */
const ORDEM_PADRAO = { by: "tier", dir: "asc" };

const CAMPOS_PREF: CampoPref[] = [
  "servidor",
  "comprarEm",
  "venderEm",
  "premium",
  "setupFee",
  "imposto",
  "focusLigado",
  "bonusDoDia",
  "taxaDaEstacao",
  "specFamilia",
  "specPorItem",
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
  // O único parâmetro que, sozinho, deixa a tabela inteira sem número.
  const faltaTaxaDaEstacao = (data?.params.missing ?? []).includes(
    "crafting.station_fee_per_100_nutrition",
  );
  const familia = FAMILIAS.find(([v]) => v === data?.family)?.[1] ?? "";

  return (
    <PageShell
      titulo="Calculador"
      descricao="Uma família por vez, todas as combinações de tier e encantamento. Edite o preço de venda ou de qualquer material e a tabela inteira recalcula. O ranking de /crafting continua respondendo outra pergunta: onde gastar o focus de hoje."
      contagem={data ? `${linhas.length} linhas de ${familia} · ${formatSilver(Number(quantidade))} un` : undefined}
      grupos={grupos(data)}
      camposPref={CAMPOS_PREF}
      filtroExtra={<CampoDeQuantidade valor={data?.params.quantity ?? 1} />}
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
      {data === null && <ApiDown falha={ultimaFalha()} />}

      {data && linhas.length === 0 && (
        <EmptyState>
          Nenhum item desta família no catálogo. Rode{" "}
          <code>python -m app.cli.import_items</code>.
        </EmptyState>
      )}

      {data && linhas.length > 0 && (
        <>
          {faltaTaxaDaEstacao && <StationFeePrompt prefs={prefs} />}
          <RetornoPainel
            retorno={data.material_return}
            opcoes={data.return_options}
            familiaLabel={familia}
            prefs={prefs}
          />
          <Parametros data={data} quantidade={Number(quantidade)} />

          <SheetTable
            columns={colunas(papeis)}
            freeze={2}
            sort={{ by: data.params.sort_by, dir: data.params.sort_dir }}
            sortDefault={ORDEM_PADRAO}
          >
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

          <ComoLer>
            <p className="max-w-prose p-4 text-note text-dim leading-relaxed">
              <b>Como ler:</b> a base é <b>uma unidade</b>, e a tabela inteira está multiplicada
              pela quantidade do filtro — agora em {formatSilver(Number(quantidade))}. Tudo que é
              soma escala junto: compra,
              gasto, focus, taxa de venda, custo, receita, lucro e investimento.{" "}
              <b>Margem, prata/focus e a margem sobre o custo não escalam</b>, porque são razões —
              ficam idênticas em 1 e em 10.000 unidades, e se mudassem seria bug.
            </p>
            <p className="max-w-prose px-4 pb-4 text-note text-dim leading-relaxed">
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
          </ComoLer>
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
    <ParamStrip>
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
      {/* Único parâmetro sem padrão. Vazio é estado legítimo aqui — quem
          explica é o painel acima da tabela (`StationFeePrompt`), e repetir a
          frase inteira aqui seria a mesma informação duas vezes na mesma tela. */}
      {p.station_fee_per_100_nutrition === null ? (
        <span className="flex items-center gap-1.5">
          <span className="lbl">taxa da loja</span>
          <span className="figure rounded-sm border border-warn px-1.5 py-px text-aux text-warn">
            desconhecida
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
          <span className="text-aux text-muted">
            assumido zero — informe nas preferências se a cidade tiver bônus hoje
          </span>
        </span>
      ) : (
        <Param
          rotulo="bônus do dia"
          valor={`+${(data.material_return.daily_bonus * 100).toFixed(0)}% em B`}
        />
      )}
      <ParamsDeTaxa fees={p.fees} />
      {!p.complete && (
        <span className="text-aux text-warn">
          falta configurar: {p.missing.join(", ")}
        </span>
      )}
    </ParamStrip>
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
      ? "lucro"
      : positivo === false
        ? "prejuizo"
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
            size={SHEET_ICON.linha}
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
          <span className="text-aux text-dim">—</span>
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
            className={`figure font-semibold text-val ${positivo ? "text-up" : "text-down"}`}
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
          <span className="block text-micro text-dim">
            ({linha.margin_on_cost_pct.toFixed(1)}%)
          </span>
        )}
      </td>

      {/* Traço aqui significava três coisas — sem histórico, giro zero, erro —
          e não distinguia nenhuma. "sem dado" diz a única que é verdade hoje:
          a coleta de histórico não passou por este item. */}
      <td
        className="figure text-aux text-dim"
        title={
          linha.days_to_sell === null
            ? "o histórico de mercado deste item ainda não foi coletado — sem ele não dá para estimar o giro"
            : "giro medido no histórico dos últimos 30 dias"
        }
      >
        {linha.days_to_sell === null ? (
          <span className="text-micro">sem dado</span>
        ) : linha.days_to_sell < 0.1 ? (
          // Arredondado, o giro alto vira "0,0 d", que se lê como ausência. O
          // que ele quer dizer é que o mercado absorve a quantidade no mesmo
          // dia — e isso é informação boa, não um zero.
          "< 1 d"
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
        <span className="text-aux text-dim">—</span>
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
 * O intervalo de preço entre as cidades, em uma linha.
 *
 * A tela mostrava só o preço **usado**, e com isso o usuário não tinha como
 * saber se a escolha economizou muito ou se foi indiferente. Intervalo grande
 * diz que vale a viagem; intervalo pequeno diz que comprar tudo numa cidade só
 * custa quase nada — a decisão que `cities_involved` já sinalizava sem o número
 * que a justifica.
 *
 * **Uma cotação só não é intervalo de zero, é falta de alternativa**, e as duas
 * coisas têm de se ler diferente: zero diria "todas as cidades cobram igual",
 * que é uma afirmação sobre o mercado; falta de alternativa é uma afirmação
 * sobre o que se sabe dele.
 */
function Faixa({ faixa }: { faixa: PriceRange | null }) {
  if (!faixa) return null;

  if (!faixa.comparable) {
    return (
      <span className="w-full text-micro text-dim">
        {faixa.fresh_city_count === 0 ? "nenhuma cotação fresca" : "1 cidade só"}
      </span>
    );
  }

  // Espalhamento pequeno não justifica viagem, e dizê-lo em âmbar seria alarme
  // falso. A cor separa "olhe para isto" de "pode ignorar".
  const vale = (faixa.spread_pct ?? 0) >= 10;
  return (
    <span className="flex w-full items-baseline gap-1 text-micro">
      <span className="figure text-dim">
        {formatSilverCompact(faixa.min_price)}–{formatSilverCompact(faixa.max_price)}
      </span>
      <span className={`figure ${vale ? "text-warn" : "text-dim"}`}>
        +{faixa.spread_pct}%
      </span>
    </span>
  );
}

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
      <span className="flex flex-col items-end gap-px text-micro text-warn leading-tight">
        {dados.map((falta) => (
          <span key={falta}>{falta}</span>
        ))}
      </span>
    );
  }

  // Falta de parâmetro é global e o painel no topo já a explica por extenso.
  // Repeti-la em vinte e três linhas seria a mesma frase vinte e três vezes —
  // a regra "nada duplicado". O traço aqui tem quem o explique logo acima.
  return (
    <span className="text-aux text-dim" title={linha.reason ?? undefined}>
      —
    </span>
  );
}

/**
 * Idade sem o "há": numa coluna, o prefixo se repete em toda linha e some do
 * olho sem parar de ocupar largura. `formatDataAge` o mantém onde a idade
 * aparece solta e precisa se anunciar como idade.
 */
function idadeCurta(segundos: number | null): string {
  return formatDataAge(segundos).replace(/^há /, "");
}

/**
 * O balão do material: cidade, preço e idade, uma linha por cidade.
 *
 * ## O que saiu, e por quê
 *
 * Saíram o id técnico, o "receita pede N", o "comprar N", o intervalo e a
 * contagem de cidades frescas. Os três do meio **já estão na célula**, e
 * repetir no balão é a regra "nada duplicado". O id e a contagem são metadado:
 * não decidem nada e empurravam para baixo as seis linhas que decidem.
 *
 * ## O que ficou
 *
 * Ordem por preço crescente, a marca na cidade em uso, e a idade — que é o que
 * separa preço bom de preço velho, e é decisão do projeto desde a fase 4.
 *
 * ## Por que monoespaçada
 *
 * As colunas são montadas com espaço, e em fonte proporcional o espaço é mais
 * estreito que o dígito: a coluna sairia torta. O preço vai alinhado à direita
 * para se comparar na vertical sem esforço — mesma razão de `.figure` existir
 * na tabela. A marca tem coluna própria, senão o nome da cidade usada nasceria
 * deslocado em relação aos outros.
 */
function balaoDeCidades(faixa: PriceRange | null): string {
  if (!faixa || faixa.cities.length === 0) return "sem cotação em nenhuma cidade";

  const linhas = faixa.cities.map((c) => ({
    marca: c.is_chosen ? "←" : c.is_manual ? "✎" : " ",
    nome: c.location_name,
    preco: formatSilverCompact(c.unit_price),
    idade: idadeCurta(c.age_seconds),
  }));

  const larguraNome = Math.max(...linhas.map((l) => l.nome.length));
  const larguraPreco = Math.max(...linhas.map((l) => l.preco.length));
  const larguraIdade = Math.max(...linhas.map((l) => l.idade.length));

  return linhas
    .map(
      (l) =>
        `${l.marca} ${l.nome.padEnd(larguraNome)}  ` +
        `${l.preco.padStart(larguraPreco)}  ${l.idade.padStart(larguraIdade)}`,
    )
    .join("\n");
}

/**
 * Um material: ícone, preço editável e o que comprar.
 *
 * A quantidade de "comprar N" é a da lista de compras — já com o retorno e
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
  const faixa = material.price_range;
  const dica = balaoDeCidades(faixa);

  return (
    <td className="l align-top">
      {/* O ícone é a âncora da coluna, e por isso vem **antes** do valor e
          colado nele. Com o bloco alinhado à direita, o número ia para a
          borda oposta e o ícone ficava solto à esquerda — de relance a coluna
          começava pelo número, que é o inverso do que o olho procura. */}
      <HoverTip dica={dica} lista className="flex w-full items-start gap-1.5">
        <ItemIcon
          url={material.icon_url}
          alt={material.item_name ?? material.item}
          tier={tier}
          size={SHEET_ICON.material}
        />
        <span className="flex min-w-0 flex-1 flex-col items-start gap-px">
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
          <span className="flex w-full items-center gap-px whitespace-nowrap text-micro">
            <span className="text-muted">comprar {formatSilver(material.buy_units)}</span>
            {/* Nome em português: é o que a busca do mercado no jogo entende,
                e aqui importa mais que em qualquer tela — esta é a lista de
                compras. */}
            <CopyButton name={material.item_name} id={material.item} />
          </span>
          <Faixa faixa={faixa} />
        </span>
      </HoverTip>
    </td>
  );
}
