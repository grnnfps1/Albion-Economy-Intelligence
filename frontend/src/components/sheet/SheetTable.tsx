/**
 * Tabela densa no modelo planilha.
 *
 * Uma coluna por grandeza, nada agrupado: quem vem de planilha encontra o
 * mesmo modelo mental, e cabe mais linha na tela do que em qualquer arranjo
 * com células compostas.
 *
 * ## `table-layout: fixed` é o ponto, não um detalhe
 *
 * Sem ele o navegador distribui a folga pelas colunas de texto — as de
 * material, que são as mais largas — e abre um vão morto antes das colunas de
 * decisão. O resultado é que "lucro" e "prata/focus", que são o motivo de a
 * tela existir, ficam empurrados para a direita e mudam de posição conforme o
 * nome do material da linha.
 *
 * Com largura fixa **por tipo de coluna**, o olho encontra cada grandeza
 * sempre no mesmo lugar. As larguras vivem em `SHEET_WIDTHS` para que todas as
 * telas usem o mesmo vocabulário: uma coluna de número tem a mesma largura em
 * /crafting e em /refining.
 */

/** Larguras por *tipo* de coluna, não por coluna. */
export const SHEET_WIDTHS = {
  /** Identidade do item: ícone, badge, nome visual e id técnico. */
  item: "20rem",
  /** Material: ícone com quantidade, preço unitário, cidade. */
  mat: "9.5rem",
  /**
   * Material, versão estreita — para receitas com muitos ingredientes.
   *
   * A partir de cinco materiais, sete colunas de 9,5rem somam 66rem e empurram
   * as colunas de decisão para fora da tela. A 6,4rem ainda cabem o ícone com a
   * quantidade e o preço unitário; o que sai é a linha da cidade, que vai para
   * o balão de hover. Preferir isto a esconder um ingrediente.
   */
  matNarrow: "6.4rem",
  /**
   * Material no calculador: precisa de mais que os outros.
   *
   * A célula carrega ícone de 30px, um campo de preço editável e a linha
   * "comprar N" — que pode ter seis dígitos. A 9,5rem do ranking o "comprar N"
   * truncava e o preço encostava na borda.
   */
  calcMat: "11.5rem",
  /** Prata. Cabe `1.683.277` sem quebrar. */
  num: "6.8rem",
  /** Percentual. */
  pct: "5.2rem",
  /** Focus e outros inteiros curtos. */
  focus: "4.6rem",
  /** Nome de cidade. */
  cidade: "8rem",
  /** Idade, giro: texto miúdo de apoio. */
  mini: "4.6rem",
} as const;

export type SheetWidth = keyof typeof SHEET_WIDTHS;

export type SheetColumn = {
  /** Rótulo do cabeçalho. Diz a consequência, não o nome do campo da API. */
  label: string;
  width: SheetWidth;
  /** Alinhamento do conteúdo. Número à direita; texto à esquerda. */
  left?: boolean;
  title?: string;
};

export function SheetTable({
  columns,
  children,
  freeze = 0,
}: {
  columns: SheetColumn[];
  children: React.ReactNode;
  /**
   * Quantas colunas da esquerda ficam presas na rolagem horizontal.
   *
   * Com doze colunas, rolar para a direita faz perder de vista **qual linha**
   * se está lendo, e a tabela vira uma grade de números sem sujeito. Prender a
   * identidade resolve, mas exige fundo opaco nas células presas — e o fundo
   * opaco apagaria o tingimento de lucro e a zebra, que são informação. O CSS
   * repinta os dois por cima (ver `.sheet-freeze` em `globals.css`), então o
   * que se perde é nada.
   */
  freeze?: number;
}) {
  // `left` de cada coluna presa é a soma das larguras das anteriores. Sai daqui
  // e não do CSS porque só aqui se sabe quais colunas a tela montou.
  const offsets: string[] = [];
  let acumulado = "0rem";
  for (let i = 0; i < freeze && i < columns.length; i += 1) {
    offsets.push(acumulado);
    acumulado = `calc(${acumulado} + ${SHEET_WIDTHS[columns[i].width]})`;
  }

  return (
    <div className="sheet-scroll">
      <table
        className={`sheet text-[11.5px] ${freeze > 0 ? "sheet-freeze" : ""}`}
        style={Object.fromEntries(
          offsets.map((left, i) => [`--freeze-${i + 1}`, left]),
        ) as React.CSSProperties}
      >
        <colgroup>
          {columns.map((c, i) => (
            <col key={`${c.label}-${i}`} style={{ width: SHEET_WIDTHS[c.width] }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={`${c.label}-${i}`} className={`lbl ${c.left ? "l" : ""}`} title={c.title}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
