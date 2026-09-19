/**
 * Exportação do recorte visível para planilha.
 *
 * Puro: entra linha, sai texto. Nada aqui toca `document` nem `window` — isso
 * mora em `download()`, no fim do arquivo, e é a única parte que o teste não
 * exercita. O resto é testado gerando o arquivo de verdade e conferindo
 * contagem de linhas, formato numérico e a fórmula da imagem.
 *
 * Por que isso merece teste: exportação é das poucas funcionalidades em que o
 * bug só aparece **depois** que o usuário abre o arquivo. Uma vírgula no lugar
 * errado não quebra a tela, não quebra o build e não aparece em nenhum log —
 * aparece como uma coluna inteira de texto no Excel de quem baixou.
 *
 * ## Três decisões de formato, e o motivo de cada uma
 *
 * - **Separador `;`**, não vírgula. O Excel em português usa a vírgula como
 *   separador decimal; um CSV com vírgula abre com tudo numa coluna só.
 * - **BOM UTF-8** no começo. Sem ele o Excel lê o arquivo como Latin-1 e
 *   "Tábuas de Adepto" vira "TÃ¡buas". O Google Sheets não precisa; o Excel
 *   precisa, e é onde a maioria vai abrir.
 * - **Decimal com vírgula e sem separador de milhar.** `1683277,5`, não
 *   `1.683.277,5`. O ponto de milhar depende de a planilha adivinhar a locale
 *   certa, e quando ela erra o número vira texto. Sem milhar não há ambiguidade.
 *   É o inverso da regra da tela, onde o número vai cheio e formatado — lá quem
 *   lê é uma pessoa, aqui é um parser.
 */

/** Uma coluna da exportação. `value` devolve o valor cru, não formatado. */
export type ExportColumn<T> = {
  header: string;
  value: (row: T) => string | number | null | undefined;
  /** Marca a coluna que vira `=IMAGE(...)` em vez de texto. */
  image?: boolean;
};

export type ExportCell = string | number | null;

/**
 * A tabela já achatada, sem função nenhuma dentro.
 *
 * Existe por causa da fronteira servidor→cliente do App Router: as telas são
 * server components e o botão de exportar é client component, e **função não
 * atravessa** essa fronteira. Passar `ExportColumn[]` direto derruba a página
 * com "Functions cannot be passed directly to Client Components" — e derruba
 * em runtime, não no build, que é o pior lugar para descobrir.
 *
 * Então o servidor achata (`toExportSheet`) e o cliente só monta o texto.
 * Como efeito colateral bom, a decisão de *quais* colunas exportar fica junto
 * da tela, onde ela pertence.
 */
export type ExportSheet = {
  headers: string[];
  rows: ExportCell[][];
  /** Índices das colunas que viram `=IMAGE(...)`. */
  imageColumns: number[];
};

/** Achata linhas + colunas numa estrutura serializável. Roda no servidor. */
export function toExportSheet<T>(rows: T[], columns: ExportColumn<T>[]): ExportSheet {
  return {
    headers: columns.map((c) => c.header),
    rows: rows.map((row) =>
      columns.map((column) => {
        const bruto = column.value(row);
        return bruto === undefined ? null : bruto;
      }),
    ),
    imageColumns: columns.flatMap((c, i) => (c.image ? [i] : [])),
  };
}

export const CSV_SEPARATOR = ";";
export const BOM = "﻿";

/**
 * Número como a planilha espera: vírgula decimal, sem separador de milhar.
 *
 * Inteiro sai sem casas decimais — `100`, não `100,0` —, porque uma coluna de
 * quantidade cheia de `,0` polui sem informar.
 */
export function formatNumberForSheet(value: number): string {
  if (!Number.isFinite(value)) return "";
  if (Number.isInteger(value)) return String(value);
  return String(value).replace(".", ",");
}

/**
 * Escapa um campo para CSV.
 *
 * Aspas duplicadas, e o campo inteiro entre aspas quando contém separador,
 * aspas ou quebra de linha. Nome de item com `;` é raro mas existe, e sem isso
 * ele deslocaria todas as colunas seguintes daquela linha — o tipo de bug que
 * só aparece numa linha em mil.
 */
export function escapeCsvField(value: string): string {
  if (!/[";\r\n]/.test(value)) return value;
  return `"${value.replace(/"/g, '""')}"`;
}

/**
 * A fórmula de imagem que Excel e Google Sheets entendem.
 *
 * A URL vai entre aspas duplas **dentro** da fórmula, então o campo inteiro
 * precisa ser escapado como CSV depois — é por isso que esta função devolve a
 * fórmula crua e não o campo pronto.
 */
export function imageFormula(url: string | null | undefined): string {
  if (!url) return "";
  return `=IMAGE("${url}")`;
}

function cell(valor: ExportCell, imagem: boolean): string {
  if (valor === null) return "";
  if (imagem) return escapeCsvField(imageFormula(String(valor)));
  if (typeof valor === "number") return formatNumberForSheet(valor);
  return escapeCsvField(valor);
}

/**
 * O CSV completo, com BOM e cabeçalho.
 *
 * Linhas separadas por CRLF: é o que o Excel espera, e o Sheets aceita os dois.
 */
export function buildCsvFromSheet(sheet: ExportSheet): string {
  const imagens = new Set(sheet.imageColumns);
  const cabecalho = sheet.headers.map(escapeCsvField).join(CSV_SEPARATOR);
  const corpo = sheet.rows.map((linha) =>
    linha.map((valor, i) => cell(valor, imagens.has(i))).join(CSV_SEPARATOR),
  );
  return BOM + [cabecalho, ...corpo].join("\r\n") + "\r\n";
}

/** Atalho de ponta a ponta. Usado pelos testes e por quem já tem as colunas. */
export function buildCsv<T>(rows: T[], columns: ExportColumn<T>[]): string {
  return buildCsvFromSheet(toExportSheet(rows, columns));
}

/**
 * Nome do arquivo, com o filtro dentro.
 *
 * O filtro no nome é o que permite ter três exportações da mesma tela na pasta
 * de downloads e saber qual é qual sem abrir. `crafting-t5-refino-2026-09-19`
 * responde sozinho; `crafting (3)` não responde nada.
 */
export function exportFilename(
  screen: string,
  filters: Record<string, string | number | null | undefined>,
  date: Date = new Date(),
): string {
  const partes = Object.entries(filters)
    .filter(([, v]) => v !== null && v !== undefined && String(v).trim() !== "")
    .map(([k, v]) => `${slug(k)}-${slug(String(v))}`);

  const dia = date.toISOString().slice(0, 10);
  return [slug(screen), ...partes, dia].join("_") + ".csv";
}

function slug(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export class ExportError extends Error {}

/**
 * Dispara o download no browser.
 *
 * Única função do módulo que toca o DOM, e a razão de ela existir separada: o
 * resto é testável sem browser.
 *
 * Se qualquer peça faltar — `Blob`, `URL.createObjectURL`, `document` —, joga
 * `ExportError` em vez de não fazer nada. **Falhar calado aqui é o pior
 * resultado possível:** o usuário clica, nada acontece, e ele não sabe se o
 * arquivo foi para algum lugar ou se o clique não pegou.
 */
export function download(filename: string, conteudo: string): void {
  if (typeof document === "undefined" || typeof Blob === "undefined") {
    throw new ExportError("exportação indisponível neste ambiente");
  }
  if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") {
    throw new ExportError("navegador sem suporte a download de arquivo gerado");
  }

  const blob = new Blob([conteudo], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}
