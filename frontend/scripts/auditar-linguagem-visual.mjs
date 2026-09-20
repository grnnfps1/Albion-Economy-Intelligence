/**
 * Auditoria da Linguagem visual, seguindo os imports.
 *
 * ## Por que existe
 *
 * A varredura da fase 38 foi feita à mão e leu **só os arquivos de página**.
 * Resultado: dois dos sete achados eram falso positivo — `/crafting` "sem
 * abreviação" usa `<Figure>`, que abrevia; `/arbitrage` "sem hierarquia" usa
 * `ProfitFigure`, que aplica `text-val`. **Auditoria que não segue o import
 * mede o arquivo, não a tela.**
 *
 * E auditoria que se refaz à mão a cada fase se degrada: a próxima é sempre um
 * pouco mais apressada que a anterior. Esta roda com `npm run auditar`.
 *
 * ## O que ela é e o que não é
 *
 * Ela lê o código, não pixels. Prova que uma tela **importa e usa** o
 * componente certo; não prova que a tela parece certa. As regras que dependem
 * de olho — ritmo vertical, se o lucro de fato salta — continuam sendo
 * checagem humana.
 *
 * ## Alvo ausente não é falha
 *
 * `ProfitFigure` em `/market` não falta: `/market` não calcula lucro. `CityTag`
 * em `/refining` não falta: ele não tem coluna de cidade. Uma regra sem alvo
 * na tela sai como `n/a`, e nunca como erro — senão a auditoria pressiona a
 * inventar coluna para satisfazer forma.
 */
import { readFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

const RAIZ = resolve(import.meta.dirname, "..", "src");

const TELAS = {
  "/market": "app/market/page.tsx",
  "/crafting": "app/crafting/page.tsx",
  "/calculadora": "app/crafting/calculadora/page.tsx",
  "/refining": "app/refining/page.tsx",
  "/arbitrage": "app/arbitrage/page.tsx",
  "/focus": "app/focus/page.tsx",
  "/agricultura": "app/farming/page.tsx",
};

/** Resolve `@/x` e `./x` para um arquivo real, com as extensões do projeto. */
function resolver(spec, deQuem) {
  const base = spec.startsWith("@/")
    ? join(RAIZ, spec.slice(2))
    : spec.startsWith(".")
      ? join(dirname(deQuem), spec)
      : null;
  if (base === null) return null; // pacote externo: fora do escopo
  for (const ext of [".tsx", ".ts", "/index.tsx", "/index.ts"]) {
    if (existsSync(base + ext)) return base + ext;
  }
  return existsSync(base) ? base : null;
}

/**
 * O código da tela **mais o de tudo que ela importa**, transitivamente.
 *
 * É a única forma de a auditoria falar sobre a tela em vez de sobre o arquivo.
 */
function codigoDaTela(caminho, vistos = new Set()) {
  const absoluto = resolve(RAIZ, caminho);
  if (vistos.has(absoluto) || !existsSync(absoluto)) return "";
  vistos.add(absoluto);

  const fonte = readFileSync(absoluto, "utf8");
  let junto = fonte;
  for (const m of fonte.matchAll(/from\s+"([^"]+)"/g)) {
    const alvo = resolver(m[1], absoluto);
    if (alvo) junto += "\n" + codigoDaTela(alvo, vistos);
  }
  return junto;
}

const tem = (s, ...nomes) => nomes.some((n) => s.includes(n));

/**
 * Cada regra tem duas perguntas, e elas olham para arquivos diferentes.
 *
 * - `alvo`: *esta tela tem esse dado?* — olha **só a página**. É propriedade
 *   da tela, não do que ela importa. A primeira versão avaliava no código
 *   completo e acusou `/market` de não tingir a linha por lucro: a palavra
 *   "lucro" vinha de um componente compartilhado, e `/market` não calcula
 *   lucro nenhum. O script reproduziu, em miniatura, o erro que ele existe
 *   para evitar.
 * - `checa`: *ela usa o jeito certo?* — olha **a tela inteira**, com os
 *   imports, porque a conformidade quase sempre mora no componente.
 *
 * Separar "cumpre" de "não se aplica" é o que impede a auditoria de virar
 * pressão para inventar conteúdo.
 */
const REGRAS = [
  {
    nome: "faixa de tier",
    checa: (s) => tem(s, "tierBorderLeft"),
  },
  {
    nome: "tingimento",
    // O alvo é **campo de dado**, não palavra. A primeira versão procurava
    // "lucro" e acusou `/market`, onde a palavra aparecia na prosa do rodapé
    // ("trocá-los inverte o sinal do lucro"). Texto explicando lucro não é a
    // mesma coisa que ter lucro para tingir.
    alvo: (s) => /\.profit|profit_per_|expected_profit/.test(s),
    checa: (s) => tem(s, "prejuizo"),
  },
  {
    nome: "cidade com ponto",
    alvo: (s) => /locationName=|city=\{/.test(s),
    checa: (s) => tem(s, "CityTag"),
  },
  {
    nome: "ambar p/ velho",
    alvo: (s) => /age_seconds|ageSeconds/.test(s),
    checa: (s) => tem(s, "AgeTag", "tomDeFrescor"),
  },
  {
    nome: "margem em pilula",
    alvo: (s) => /margin_pct/.test(s),
    checa: (s) => tem(s, "ProfitFigure"),
  },
  {
    nome: "hierarquia",
    checa: (s) => /text-val/.test(s),
  },
  {
    nome: "id no tooltip",
    // O id técnico nunca aparece como linha própria da célula.
    checa: (s) => !/text-micro text-dim">\{\w+\.item\}/.test(s),
  },
  {
    nome: "abreviacao",
    alvo: (s) => /material_cost|input_cost|gross_revenue|median_30d|buy_price/.test(s),
    checa: (s) => tem(s, "formatSilverCompact"),
  },
  {
    nome: "sem px avulso",
    // Só na tela: os literais que sobram em `globals.css` são a definição dos
    // tokens, e é lá que eles devem estar.
    checaSoNaPagina: true,
    checa: (s) => !/text-\[|rounded-\[[0-9]|px-\[[0-9]|bg-\[linear/.test(s),
  },
];

let falhas = 0;
const larguraNome = 14;
const cabecalho =
  "tela".padEnd(larguraNome) + REGRAS.map((r) => r.nome.padEnd(17)).join("");
console.log(cabecalho);
console.log("-".repeat(cabecalho.length));

for (const [nome, caminho] of Object.entries(TELAS)) {
  const completo = codigoDaTela(caminho);
  const pagina = readFileSync(resolve(RAIZ, caminho), "utf8");
  const celulas = REGRAS.map((regra) => {
    if (regra.alvo && !regra.alvo(pagina)) return "n/a";
    if (regra.checa(regra.checaSoNaPagina ? pagina : completo)) return "ok";
    falhas += 1;
    return "FALHA";
  });
  console.log(nome.padEnd(larguraNome) + celulas.map((c) => c.padEnd(17)).join(""));
}

console.log();
if (falhas === 0) {
  console.log("Nenhuma regra violada. `n/a` = a regra não tem alvo nesta tela.");
} else {
  console.log(`${falhas} violação(ões).`);
}
// Sai com erro para poder entrar no CI sem virar aviso que ninguém lê.
process.exit(falhas === 0 ? 0 : 1);
