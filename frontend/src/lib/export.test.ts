/**
 * Exportação: o arquivo é gerado de verdade e conferido.
 *
 * Exportação é das poucas funcionalidades em que o bug só aparece depois que o
 * usuário abre o arquivo — não quebra a tela, não quebra o build, não aparece
 * em log. Por isso aqui o teste monta o CSV inteiro e lê o resultado linha a
 * linha, em vez de verificar que a função foi chamada.
 */

import { describe, expect, it } from "vitest";

import {
  BOM,
  buildCsv,
  escapeCsvField,
  exportFilename,
  formatNumberForSheet,
  imageFormula,
  type ExportColumn,
} from "./export";

type Linha = {
  item: string;
  nome: string;
  icone: string | null;
  lucro: number;
  margem: number;
  focus: number | null;
};

const LINHAS: Linha[] = [
  {
    item: "T4_PLANKS",
    nome: "Tábuas de Adepto",
    icone: "https://render.albiononline.com/v1/item/T4_PLANKS.png?quality=1&size=64",
    lucro: 1683277,
    margem: 18.4,
    focus: 93,
  },
  {
    item: "T5_PLANKS",
    nome: "Tábuas de Especialista",
    icone: "https://render.albiononline.com/v1/item/T5_PLANKS.png?quality=1&size=64",
    lucro: -240.5,
    margem: -3.25,
    focus: null,
  },
];

const COLUNAS: ExportColumn<Linha>[] = [
  { header: "imagem", value: (l) => l.icone, image: true },
  { header: "id", value: (l) => l.item },
  { header: "nome", value: (l) => l.nome },
  { header: "lucro", value: (l) => l.lucro },
  { header: "margem %", value: (l) => l.margem },
  { header: "focus", value: (l) => l.focus },
];

function linhasDe(csv: string): string[] {
  return csv.replace(BOM, "").trimEnd().split("\r\n");
}

/**
 * Parser de CSV do próprio teste.
 *
 * Existe para que a verificação seja "uma planilha consegue ler isto de volta"
 * e não "a string contém o que eu escrevi". Um `split(";")` ingênuo passaria
 * justamente no caso que este arquivo precisa pegar: campo com o separador
 * dentro dele.
 */
function camposDe(linha: string): string[] {
  const campos: string[] = [];
  let atual = "";
  let dentroDeAspas = false;
  for (let i = 0; i < linha.length; i++) {
    const c = linha[i];
    if (dentroDeAspas) {
      if (c === '"' && linha[i + 1] === '"') {
        atual += '"';
        i++;
      } else if (c === '"') {
        dentroDeAspas = false;
      } else {
        atual += c;
      }
    } else if (c === '"') {
      dentroDeAspas = true;
    } else if (c === ";") {
      campos.push(atual);
      atual = "";
    } else {
      atual += c;
    }
  }
  campos.push(atual);
  return campos;
}

describe("contagem de linhas", () => {
  it("tem uma linha de cabeçalho mais uma por registro", () => {
    const linhas = linhasDe(buildCsv(LINHAS, COLUNAS));
    expect(linhas).toHaveLength(LINHAS.length + 1);
  });

  it("exporta o recorte que recebeu, não o conjunto inteiro", () => {
    const recorte = LINHAS.slice(0, 1);
    expect(linhasDe(buildCsv(recorte, COLUNAS))).toHaveLength(2);
  });

  it("lista vazia ainda traz o cabeçalho", () => {
    // Arquivo sem cabeçalho nenhum não diz ao usuário que o filtro zerou.
    expect(linhasDe(buildCsv([], COLUNAS))).toEqual(["imagem;id;nome;lucro;margem %;focus"]);
  });

  it("toda linha tem o mesmo número de campos que o cabeçalho", () => {
    const linhas = linhasDe(buildCsv(LINHAS, COLUNAS));
    for (const linha of linhas) {
      expect(camposDe(linha)).toHaveLength(COLUNAS.length);
    }
  });
});

describe("formato numérico", () => {
  it("decimal usa vírgula, porque o separador de campo é ponto e vírgula", () => {
    expect(formatNumberForSheet(18.4)).toBe("18,4");
    expect(formatNumberForSheet(-3.25)).toBe("-3,25");
  });

  it("inteiro sai sem casas decimais", () => {
    expect(formatNumberForSheet(1683277)).toBe("1683277");
  });

  it("não usa separador de milhar", () => {
    /**
     * `1.683.277` dependeria de a planilha adivinhar a locale certa, e quando
     * ela erra o número inteiro vira texto — a coluna some do somatório sem
     * avisar.
     */
    expect(formatNumberForSheet(1683277)).not.toContain(".");
    expect(formatNumberForSheet(1683277.5)).toBe("1683277,5");
  });

  it("número entra no CSV como número, nunca entre aspas", () => {
    const linha = linhasDe(buildCsv([LINHAS[0]], COLUNAS))[1];
    const campos = camposDe(linha);
    expect(campos[3]).toBe("1683277");
    expect(campos[4]).toBe("18,4");
    // Sem aspas no texto cru: planilha nenhuma pode ler isto como texto.
    expect(linha).toContain(";1683277;18,4;");
  });

  it("nulo vira campo vazio, não zero", () => {
    // Regra 1 do projeto, e aqui ela também importa: um zero exportado soma no
    // somatório da planilha e inventa um total que não existe.
    const linha = linhasDe(buildCsv([LINHAS[1]], COLUNAS))[1];
    expect(camposDe(linha)[5]).toBe("");
  });

  it("negativo mantém o sinal", () => {
    const linha = linhasDe(buildCsv([LINHAS[1]], COLUNAS))[1];
    expect(camposDe(linha)[3]).toBe("-240,5");
  });
});

describe("fórmula da imagem", () => {
  it("gera =IMAGE com a url entre aspas", () => {
    expect(imageFormula("https://x/y.png")).toBe('=IMAGE("https://x/y.png")');
  });

  it("no CSV a fórmula fica escapada e continua válida", () => {
    /**
     * A URL vai entre aspas dentro da fórmula, e o campo inteiro precisa ser
     * escapado depois. Sem a duplicação das aspas, a planilha lê a fórmula
     * truncada e a coluna de imagem fica vazia em todas as linhas.
     */
    const linha = linhasDe(buildCsv([LINHAS[0]], COLUNAS))[1];
    // Cru: as aspas da URL estão duplicadas e o campo inteiro está entre aspas.
    expect(linha.startsWith('"=IMAGE(""https://render')).toBe(true);
    // Lido de volta como uma planilha leria: a fórmula original, intacta.
    expect(camposDe(linha)[0]).toBe(
      '=IMAGE("https://render.albiononline.com/v1/item/T4_PLANKS.png?quality=1&size=64")',
    );
  });

  it("item sem ícone gera campo vazio, não uma fórmula quebrada", () => {
    const semIcone: Linha = { ...LINHAS[0], icone: null };
    const campo = camposDe(linhasDe(buildCsv([semIcone], COLUNAS))[1])[0];
    expect(campo).toBe("");
  });
});

describe("escape", () => {
  it("nome com ponto e vírgula não desloca as colunas seguintes", () => {
    const perigoso: Linha = { ...LINHAS[0], nome: "Tábuas; especiais" };
    const linha = linhasDe(buildCsv([perigoso], COLUNAS))[1];
    const campos = camposDe(linha);
    // O que importa não é a string: é a planilha ainda achar seis colunas.
    expect(campos).toHaveLength(COLUNAS.length);
    expect(campos[2]).toBe("Tábuas; especiais");
    expect(campos[3]).toBe("1683277");
  });

  it("aspas no texto são duplicadas", () => {
    expect(escapeCsvField('diz "oi"')).toBe('"diz ""oi"""');
  });

  it("texto simples não ganha aspas à toa", () => {
    expect(escapeCsvField("Tábuas de Adepto")).toBe("Tábuas de Adepto");
  });
});

describe("arquivo", () => {
  it("começa com BOM, senão o Excel lê como Latin-1", () => {
    const csv = buildCsv(LINHAS, COLUNAS);
    expect(csv.startsWith(BOM)).toBe(true);
    // E o acento sobrevive à ida e volta.
    expect(csv).toContain("Tábuas de Adepto");
  });

  it("usa ponto e vírgula como separador", () => {
    expect(linhasDe(buildCsv(LINHAS, COLUNAS))[0]).toBe("imagem;id;nome;lucro;margem %;focus");
  });

  it("separa linhas com CRLF", () => {
    expect(buildCsv(LINHAS, COLUNAS)).toContain("\r\n");
  });
});

describe("nome do arquivo", () => {
  const dia = new Date("2026-09-19T12:00:00Z");

  it("carrega o filtro, para três exportações da mesma tela serem distinguíveis", () => {
    expect(exportFilename("crafting", { tier: 5, tipo: "refino" }, dia)).toBe(
      "crafting_tier-5_tipo-refino_2026-09-19.csv",
    );
  });

  it("filtro vazio não vira sujeira no nome", () => {
    expect(exportFilename("market", { tier: "", busca: null, enc: undefined }, dia)).toBe(
      "market_2026-09-19.csv",
    );
  });

  it("acento e espaço viram slug", () => {
    expect(exportFilename("refino", { cidade: "Fort Sterling" }, dia)).toBe(
      "refino_cidade-fort-sterling_2026-09-19.csv",
    );
  });
});
