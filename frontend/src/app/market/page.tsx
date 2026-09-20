import { ExportButton } from "@/components/sheet/ExportButton";
import { SHEET_ICON } from "@/components/sheet/Chrome";
import { SheetTable, type SheetColumn } from "@/components/sheet/SheetTable";
import { CopyButton } from "@/components/sheet/CopyButton";
import { ApiDown, EmptyState } from "@/components/ui/EmptyState";
import { PageShell } from "@/components/PageShell";
import { Param, ParamStrip } from "@/components/sheet/Chrome";
import { ComoLer } from "@/components/sheet/ComoLer";
import { CityTag, QualityBadge, TierBadge } from "@/components/ui/Badges";
import { AgeTag } from "@/components/ui/Figures";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { fetchMarketPrices, type MarketPrice, type PriceField,
  ultimaFalha,
} from "@/lib/api";
import { toExportSheet, type ExportColumn } from "@/lib/export";
import { formatSilver, formatSilverCompact } from "@/lib/format";
import { getPreferences } from "@/lib/preferences";
import { tierBorderLeft } from "@/lib/tiers";

export const dynamic = "force-dynamic";

/**
 * Uma coluna por grandeza, largura fixa por tipo de coluna.
 *
 * Os rótulos dizem a consequência — "você paga", "você recebe" — e não o nome
 * do campo na API. `sell_min` isolado não diz nada a ninguém.
 */
const COLUNAS: SheetColumn[] = [
  { label: "item", width: "item", left: true },
  { label: "você paga", width: "num", title: "ordem de venda mais barata: o que sai do bolso" },
  { label: "venda máx", width: "num" },
  { label: "você recebe", width: "num", title: "ordem de compra mais alta: o que entra ao vender" },
  { label: "compra mín", width: "num" },
  { label: "mediana 30d", width: "num" },
  { label: "vs mediana", width: "pct" },
  { label: "giro", width: "mini" },
  { label: "cobertura", width: "mini" },
];

const GRUPOS = [
  {
    /**
     * `/market` **mantém a pílula**, e é a única das telas densas que mantém.
     *
     * Decidido em 19/09/2026, quando as outras migraram para `SortHeader`. O
     * motivo é estrutural, não de gosto: as colunas desta tela são **blocos
     * compostos** — "comprando agora" mostra `sell_min` e `sell_max` juntos,
     * "vendendo agora" mostra `buy_max` e `buy_min`. As ordenações são por
     * *um* desses valores, e um cabeçalho que contém dois números não pode
     * dizer por qual deles está ordenando sem ficar ambíguo.
     *
     * Separar os blocos em colunas simples resolveria a ambiguidade e mudaria
     * a leitura de uma tela que funciona: o par lado a lado é o que permite
     * ver o spread de relance, e essa é a razão de a tela existir assim.
     * Trocar isso por uniformidade de mecanismo seria pagar caro pelo barato.
     */
    chave: "sort_by", padrao: "item",
    opcoes: [
      { valor: "item", rotulo: "item" },
      { valor: "sell_price_min", rotulo: "compra" },
      { valor: "buy_price_max", rotulo: "venda" },
      { valor: "observed_at", rotulo: "coleta" },
    ],
  },
  {
    chave: "tier", padrao: "",
    opcoes: [
      { valor: "", rotulo: "todos" },
      ...[4, 5, 6, 7, 8].map((t) => ({ valor: String(t), rotulo: `T${t}` })),
    ],
  },
  {
    chave: "enchantment", padrao: "",
    opcoes: [
      { valor: "", rotulo: "encanto" },
      ...[0, 1, 2, 3, 4].map((e) => ({ valor: String(e), rotulo: `.${e}` })),
    ],
  },
];

/**
 * O que vai para a planilha.
 *
 * Valores **crus**, não formatados: quem abre o arquivo quer somar e ordenar.
 * A formatação da tela é para o olho humano; aqui quem lê é um parser.
 */
const EXPORTACAO: ExportColumn<MarketPrice>[] = [
  { header: "imagem", value: (p) => p.icon_url, image: true },
  { header: "id", value: (p) => p.item },
  { header: "nome", value: (p) => p.item_name },
  { header: "tier", value: (p) => p.tier },
  { header: "encanto", value: (p) => p.enchantment },
  { header: "cidade", value: (p) => p.location },
  { header: "qualidade", value: (p) => p.quality },
  { header: "você paga", value: (p) => p.sell_min.value },
  { header: "preço manual?", value: (p) => (p.sell_min.is_manual ? "sim" : "não") },
  { header: "venda máx", value: (p) => p.sell_max.value },
  { header: "você recebe", value: (p) => p.buy_max.value },
  { header: "compra mín", value: (p) => p.buy_min.value },
  { header: "mediana 30d", value: (p) => p.median_30d },
  { header: "vs mediana %", value: (p) => p.vs_median_pct },
  { header: "giro/dia", value: (p) => p.liquidity.units_per_day },
  { header: "dias com dado", value: (p) => p.liquidity.days_with_data },
  { header: "idade (s)", value: (p) => p.sell_min.age_seconds },
];

export default async function MarketPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const query = Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]),
  ) as Record<string, string | undefined>;

  const prefs = await getPreferences();
  const page = await fetchMarketPrices({ server: prefs.server, ...query, limit: "40" });

  return (
    <PageShell
      titulo="Mercado"
      descricao="Preço fresco num mercado que quase ninguém abre continua sendo preço frágil. Por isso a idade e a cobertura do histórico aparecem em toda linha."
      contagem={page ? `${page.prices.length} de ${formatSilver(page.total)} cotações` : undefined}
      grupos={GRUPOS}
      prefs={prefs}
      acoes={
        <ExportButton
          sheet={toExportSheet(page?.prices ?? [], EXPORTACAO)}
          screen="market"
          filters={{
            servidor: prefs.server,
            busca: query.search,
            tier: query.tier,
            encanto: query.enchantment,
          }}
        />
      }
    >
      {page === null && <ApiDown falha={ultimaFalha()} />}

      {page?.total === 0 && (
        <EmptyState>
          Nenhum preço para este recorte. Pode ser banco vazio — rode a coleta — ou mercado que
          ninguém abriu no jogo. Ausência de cotação não é preço baixo.
        </EmptyState>
      )}

      {/* `/market` não calcula lucro, então não tem imposto nem setup fee a
          mostrar — mas tem a mesma faixa, no mesmo lugar e com a mesma altura.
          Ela diz o que **recorta** a tabela, que é o equivalente aqui. */}
      {page && page.total > 0 && (
        <ParamStrip>
          <Param rotulo="servidor" valor={prefs.server} />
          <Param rotulo="mediana" valor="30 d"
            dica="a janela da referência: mediana de 30 dias, e não média — um preço manipulado contamina a média inteira" />
          <Param rotulo="cotações" valor={formatSilver(page.total)} />
        </ParamStrip>
      )}

      {page && page.total > 0 && (
        <SheetTable columns={COLUNAS}>
          {page.prices.map((p) => (
            <MarketLine key={`${p.item}-${p.location}-${p.quality}`} price={p} />
          ))}
        </SheetTable>
      )}

      {page && page.total > 0 && (
        <ComoLer>
          <p className="max-w-prose p-4 text-note text-dim leading-relaxed">
            <b>Como ler:</b> <i>comprando agora</i> é o que você <b>paga</b> e{" "}
            <i>vendendo agora</i> é o que você <b>recebe</b> — são preços diferentes, e
            trocá-los inverte o sinal do lucro. A referência é a <b>mediana</b> de 30 dias,
            não a média: o histórico do AODP já vem em média por dia, e um único preço
            manipulado contamina a janela inteira. Frescor e cobertura andam juntos de
            propósito: <i>há 8 min</i> ao lado de <i>3/30d</i> é um alerta, não um elogio —
            preço fresco em mercado que ninguém visita é preço frágil.
          </p>
        </ComoLer>
      )}
    </PageShell>
  );
}

/**
 * Um preço da linha.
 *
 * Três estados, e os três precisam ser distinguíveis de relance:
 *
 * - **coletado**: o normal;
 * - **manual**: o usuário informou e ele venceu. Marcado, com o coletado
 *   riscado ao lado — ver os dois é o que permite perceber um zero a mais;
 * - **manual expirado**: existe preço manual, mas passou do frescor e o
 *   coletado voltou. Dito em âmbar, porque ignorar em silêncio faria o usuário
 *   achar que o dele ainda vale.
 */
function Preco({ campo }: { campo: PriceField }) {
  if (campo.value === null) {
    return (
      <td>
        <span className="text-aux text-dim">sem dado</span>
        {campo.manual_expired && <ManualExpirado />}
      </td>
    );
  }
  return (
    <td>
      <span className="flex items-baseline justify-end gap-1">
        {campo.is_manual && (
          <span
            className="rounded-sm border border-warn px-1 text-micro leading-tight text-warn"
            title="preço que você informou — vence o coletado enquanto for fresco"
          >
            SEU
          </span>
        )}
        {/* Hierarquia por tamanho: estes são os números que a tela existe
            para comparar. Estavam com o mesmo peso de todo o resto, e
            tudo com o mesmo peso é o mesmo que nada ter peso. */}
        <span className="figure text-val">{formatSilverCompact(campo.value)}</span>
      </span>
      {campo.is_manual && campo.collected_value !== null && (
        <span
          className="figure block text-micro text-dim line-through"
          title="o que a coleta dizia"
        >
          {formatSilver(campo.collected_value)}
        </span>
      )}
      <span className="block">
        <AgeTag seconds={campo.age_seconds} freshness={campo.freshness} />
      </span>
      {campo.manual_expired && <ManualExpirado />}
    </td>
  );
}

function ManualExpirado() {
  return (
    <span
      className="block text-micro text-warn"
      title="você informou um preço aqui, mas ele passou do limite de frescor e o coletado voltou"
    >
      manual expirado
    </span>
  );
}

function MarketLine({ price }: { price: MarketPrice }) {
  const distancia = price.vs_median_pct;
  const liq = price.liquidity;
  const cobertura = liq.status === "KNOWN" ? liq.days_with_data / liq.period_days : 0;

  return (
    <tr>
      {/* A faixa de tier: `.sheet` dá a largura, o token dá a cor. */}
      <td className={`l ${tierBorderLeft(price.tier)}`}>
        <span className="flex min-w-0 items-center gap-2">
          <ItemIcon
            url={price.icon_url}
            alt={price.item_name ?? price.item}
            tier={price.tier}
            size={SHEET_ICON.linha}
          />
          <span className="min-w-0">
            <span className="flex items-center gap-1">
              <TierBadge tier={price.tier} enchantment={price.enchantment} />
              <QualityBadge quality={price.quality} />
              <CityTag city={price.location} className="text-micro text-muted" />
            </span>
            <span className="flex min-w-0 items-center">
              {/* Nome visual manda, id técnico no tooltip — a regra do briefing do
                  redesign. O id saiu da segunda linha: ele não decide nada, e
                  ocupava uma linha inteira da célula mais estreita da tabela.
                  Continua a um hover daqui, e no alt+clique do botão copiar. */}
              <span className="truncate" title={price.item}>
                {price.item_name ?? price.item}
              </span>
              {/* Colado no nome, não na borda da célula, e visível sempre. */}
              <CopyButton name={price.item_name} id={price.item} />
            </span>
          </span>
        </span>
      </td>

      <Preco campo={price.sell_min} />
      <Preco campo={price.sell_max} />
      <Preco campo={price.buy_max} />
      <Preco campo={price.buy_min} />

      <td className="figure">
        {price.median_30d === null ? "—" : formatSilverCompact(price.median_30d)}
      </td>

      <td
        className={`figure ${
          distancia === null
            ? "text-dim"
            : distancia <= -5
              ? "text-up"
              : distancia >= 5
                ? "text-down"
                : "text-dim"
        }`}
        title="distância do preço de compra imediata até a mediana"
      >
        {distancia === null ? "—" : `${distancia > 0 ? "+" : ""}${distancia.toFixed(1)}%`}
      </td>

      <td className="figure text-aux">
        {liq.status === "UNKNOWN" ? (
          <span className="text-dim" title="sem histórico suficiente para medir giro">
            —
          </span>
        ) : (
          <>
            {formatSilver(liq.units_per_day)}
            <span className="text-micro text-dim">/d</span>
          </>
        )}
      </td>

      <td>
        {liq.status === "UNKNOWN" ? (
          <span className="text-aux text-dim">desconhecida</span>
        ) : (
          <>
            <span className="figure text-aux text-dim">
              {liq.days_with_data}/{liq.period_days}d
            </span>
            <span className="ml-auto block h-[3px] w-10 overflow-hidden rounded-full bg-line">
              <span
                className={`block h-full ${
                  cobertura >= 0.7 ? "bg-up" : cobertura >= 0.3 ? "bg-warn" : "bg-down"
                }`}
                style={{ width: `${cobertura * 100}%` }}
              />
            </span>
          </>
        )}
      </td>
    </tr>
  );
}
