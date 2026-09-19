import { CopyButton } from "@/components/sheet/CopyButton";
import { SHEET_ICON } from "@/components/sheet/Chrome";
import { HoverTip } from "@/components/sheet/HoverTip";
import { SHEET_WIDTHS, type SheetColumn, type SheetWidth } from "@/components/sheet/SheetTable";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { formatSilver } from "@/lib/format";

/**
 * Um material, numa coluna só dele.
 *
 * A decisão de fundo: **uma coluna por material** em vez de todos empilhados
 * numa célula. Quem vem de planilha encontra o mesmo modelo mental, e comparar
 * o preço do mesmo material entre duas linhas vira uma leitura vertical em vez
 * de uma caça dentro de uma célula composta.
 *
 * Três detalhes que vieram da iteração:
 *
 * - **O nome só aparece no balão de hover.** Ele é longo e roubaria a largura
 *   das colunas de decisão, que são o motivo de a tela existir. Sem ele, porém,
 *   o ícone sozinho obriga a decorar arte — daí o balão, e não o `title`
 *   nativo, que demora quase um segundo e some ao mover o mouse.
 * - **O badge do ícone é a quantidade; o texto é o preço unitário.** Nada
 *   duplicado: repetir a quantidade nos dois gasta espaço e confunde.
 * - **O botão de copiar fica encostado no preço**, não na borda da célula, e
 *   visível sempre.
 */

/**
 * Teto de colunas de material.
 *
 * Sete é o máximo real do dump, conferido contra o banco — e é também o limite
 * que a planilha de referência usa (`Quant_R1..R7`). Não é um número escolhido:
 * é o maior que existe.
 */
export const MAX_MATERIAL_COLUMNS = 7;

/** A partir daqui a coluna encolhe, para as colunas de decisão não saírem da tela. */
const LIMIAR_ESTREITO = 5;

/**
 * Quantas colunas de material abrir, dado o que as linhas visíveis usam.
 *
 * Adaptativo de propósito: hoje as receitas rastreadas têm no máximo 3
 * materiais, então a tabela abre 3 e não desperdiça largura. Se comida e poções
 * entrarem no conjunto rastreado — elas chegam a 7 —, a tabela acompanha sozinha
 * em vez de truncar em silêncio.
 */
export function materialColumnCount(counts: number[]): number {
  return Math.min(MAX_MATERIAL_COLUMNS, Math.max(1, ...counts, 1));
}

/** Largura da coluna de material, dada a quantidade de colunas abertas. */
export function materialWidth(columnCount: number): SheetWidth {
  return columnCount >= LIMIAR_ESTREITO ? "matNarrow" : "mat";
}

/** As colunas de material prontas para o cabeçalho. */
export function materialColumns(columnCount: number, label = "mat."): SheetColumn[] {
  const width = materialWidth(columnCount);
  return Array.from({ length: columnCount }, (_, i) => ({
    label: `${label} ${i + 1}`,
    width,
    left: true,
  }));
}

export function MaterialCell({
  item,
  itemName,
  iconUrl,
  quantity,
  unitPrice,
  tier,
  locationName,
  isAlternateCity = false,
  tip,
  compact = false,
}: {
  item: string;
  itemName: string | null;
  iconUrl: string | null;
  quantity: number;
  unitPrice: number | null;
  tier: number | null;
  locationName: string | null;
  isAlternateCity?: boolean;
  /** Texto do balão. Cai no nome do item quando não informado. */
  tip?: string;
  /** Versão estreita: a cidade sai da célula e vai para o balão. */
  compact?: boolean;
}) {
  const nome = itemName ?? item;
  const cidade = locationName ?? "—";
  // No modo estreito a cidade some da célula, então ela precisa estar no balão
  // — senão a informação desaparece em vez de mudar de lugar.
  const balao = tip ?? `${nome} · ${item}`;

  return (
    <td className="l">
      <HoverTip
        dica={compact ? `${balao} · comprar em ${cidade}` : balao}
        className="flex min-w-0 items-center gap-1.5"
      >
        <ItemIcon url={iconUrl} alt={nome} tier={tier} quantity={quantity} size={SHEET_ICON.material} />
        <span className="min-w-0">
          <span className="flex items-center">
            <span className="figure">{formatSilver(unitPrice)}</span>
            <CopyButton name={itemName} id={item} />
          </span>
          {compact ? (
            // Sem espaço para o nome da cidade, mas o aviso de cidade
            // alternativa é decisão — vira um ponto âmbar.
            isAlternateCity && (
              <span className="block text-micro text-warn" aria-label={`comprar em ${cidade}`}>
                ● outra cidade
              </span>
            )
          ) : (
            <span
              className={`block truncate text-micro ${
                isAlternateCity ? "text-warn" : "text-dim"
              }`}
            >
              {cidade}
            </span>
          )}
        </span>
      </HoverTip>
    </td>
  );
}

/** Célula vazia, para receitas com menos materiais que o máximo da tabela. */
export function EmptyMaterialCell() {
  return <td className="l text-dim">—</td>;
}

/**
 * Aviso de ingrediente que não coube.
 *
 * Existe para que a omissão **nunca** seja silenciosa. Hoje não dispara: o
 * máximo real é 7 e a tabela abre até 7. Se o dump ganhar uma receita de 8, a
 * linha diz que há mais em vez de mentir sobre a receita — que é a regra que
 * motivou esta mudança.
 */
export function MaterialOverflow({ extras, names }: { extras: number; names: string[] }) {
  if (extras <= 0) return null;
  return (
    <span
      className="figure ml-1 rounded-sm border border-warn px-1 text-micro text-warn"
      title={`Esta receita tem mais ${extras} ingrediente(s) que não cabem na tabela: ${names.join(", ")}. O custo já os inclui.`}
    >
      +{extras}
    </span>
  );
}

/** Reexportado para as telas montarem o `colgroup` sem importar de dois lugares. */
export { SHEET_WIDTHS };
