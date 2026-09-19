/**
 * Tipos e padrões das preferências.
 *
 * Módulo separado de propósito: o formulário é client component e não pode
 * importar nada que puxe `next/headers`. Misturar os dois arrasta o módulo de
 * servidor para dentro do bundle do browser e o build falha.
 *
 * Os padrões são o que a comunidade reporta, e **não foram verificados no
 * jogo** (docs/04-taxas.md). A diferença em relação a inventar um número é que
 * a interface diz isso e deixa ajustar.
 */
export type Preferences = {
  server: string;
  buyLocation: string;
  sellLocation: string;
  premium: boolean;
  setupFeePct: number;
  salesTaxPct: number;
  returnRate: number;
  /**
   * Prata por 100 de nutrição que a estação cobra — o número que o jogador lê
   * na tela da estação. A taxa real sai de `item_value × 0,1125 × isto ÷ 100`,
   * e por isso escala com tier e encantamento.
   *
   * **`null` é o padrão, e é deliberado.** Este é o único parâmetro da tela que
   * não vem pré-preenchido, contra a convenção do resto das preferências. O
   * motivo está em `docs/04-taxas.md` §11: não existe valor defensável para pôr
   * aqui, e o número está escrito na tela da estação — é o mais fácil de obter
   * da lista inteira de medições.
   */
  stationFeePer100Nutrition: number | null;
  focusBudget: number;
  /**
   * Focus que **regenera por dia** — 10.000 numa conta Premium.
   *
   * Não é o mesmo que `focusBudget`, e misturar os dois erraria a conta:
   * `focusBudget` é o **estoque** disponível agora (pode chegar a 30.000
   * acumulados) e serve para "o que faço com o que tenho"; este é a **taxa**, e
   * é o que limita quanto se produz num dia típico.
   *
   * É o que torna craft e refino comparáveis com a fazenda: os dois lados
   * passam a responder "quanto rende um dia disto".
   */
  focusPerDay: number;
  quantity: number;
  /**
   * Probabilidade de perder a carga na rota, por zona.
   *
   * Preferência como as taxas, mas com padrão **zero** em vez de "não
   * verificado": zero significa "não estou modelando perda", e o lucro
   * ajustado sai idêntico ao bruto — à vista, sem esconder nada. Quem já
   * perdeu carga sabe o próprio número melhor que qualquer padrão.
   */
  lossPctBlue: number;
  lossPctRedBlack: number;
  /**
   * Focus ligado troca a coluna da matriz de retorno; o bônus diário (0, 10%
   * ou 20%) é o que o jogo sorteia por dia e soma à célula.
   */
  useFocus: boolean;
  dailyProductionBonus: number;
  /**
   * Nível de especialização (0–100) por família de recurso.
   *
   * Por família e não item a item: a planilha do Albion VIP faz item a item,
   * mas isso seriam centenas de campos para uma decisão que quase ninguém toma
   * item a item — quem especializa couro especializa a linha inteira.
   *
   * Zero **não** é "não informado": é "não especializado", e o custo em Focus
   * sai igual ao do dump. A tela diz que a conta assumiu spec 0.
   */
  specLeather: number;
  specCloth: number;
  specPlanks: number;
  specMetalbar: number;
  specStoneblock: number;
  /**
   * Especialização por **item**, para craft de equipamento.
   *
   * Refino é por família — quem especializa couro especializa a linha. Craft
   * não: quem especializou Capuz de Mercenário não especializou Capuz de
   * Caçador, porque são nós diferentes do Destiny Board.
   *
   * É uma lista aberta e não um conjunto de campos fixos: quem crafta duas
   * peças informa duas, quem crafta vinte informa vinte. Item que não estiver
   * aqui fica em zero, com o aviso de sempre.
   */
  specItems: SpecItem[];
};

/** Um item especializado: a linha do item e o nível de 0 a 100. */
export type SpecItem = { item: string; level: number };

export const DEFAULTS: Preferences = {
  server: "west",
  buyLocation: "caerleon",
  sellLocation: "caerleon",
  premium: true,
  setupFeePct: 0.025,
  salesTaxPct: 0.04,
  returnRate: 0.15,
  // UNKNOWN de propósito. O 1.666 que ficava aqui saiu da mediana de taxas
  // implicadas por uma reconstrução que se provou inválida, e o 184 da planilha
  // é a escolha de estação de **um** jogador. Nenhum dos dois é constante do
  // jogo, e inventar um seria quebrar a regra 2.
  stationFeePer100Nutrition: null,
  focusBudget: 10_000,
  // Geração diária de uma conta Premium. Diferente dos outros padrões, este
  // tem fonte: docs/05-custo-de-focus.md, "Orçamento de Focus".
  focusPerDay: 10_000,
  quantity: 100,
  lossPctBlue: 0,
  lossPctRedBlack: 0,
  useFocus: false,
  dailyProductionBonus: 0,
  specLeather: 0,
  specCloth: 0,
  specPlanks: 0,
  specMetalbar: 0,
  specStoneblock: 0,
  specItems: [],
};

export const COOKIE = "aei_prefs";

/** Parâmetros de taxa para os endpoints. Todas as telas usam o mesmo conjunto. */
export function feeParams(prefs: Preferences): Record<string, string> {
  return {
    server: prefs.server,
    setup_fee_pct: String(prefs.setupFeePct),
    sales_tax_pct: String(prefs.salesTaxPct),
    premium: String(prefs.premium),
    // `return_rate` não vai mais por padrão: a matriz por (cidade, atividade,
    // Focus) é o valor primário, e mandar um número fixo aqui sobrescreveria
    // justamente o que a fase resolveu.
    // Não informado não vira zero nem palpite: o parâmetro simplesmente não
    // é enviado, e o backend responde UNKNOWN dizendo o que preencher.
    ...(prefs.stationFeePer100Nutrition === null ||
    prefs.stationFeePer100Nutrition === undefined
      ? {}
      : {
          station_fee_per_100_nutrition: String(prefs.stationFeePer100Nutrition),
        }),
    use_focus: String(prefs.useFocus),
    daily_production_bonus: String(prefs.dailyProductionBonus),
    loss_pct_blue: String(prefs.lossPctBlue),
    loss_pct_red_black: String(prefs.lossPctRedBlack),
    spec_leather: String(prefs.specLeather),
    spec_cloth: String(prefs.specCloth),
    spec_planks: String(prefs.specPlanks),
    spec_metalbar: String(prefs.specMetalbar),
    spec_stoneblock: String(prefs.specStoneblock),
    // `id:nivel` separados por vírgula. Itens sem nível não são enviados: zero
    // é o padrão do backend, e mandá-lo explicitamente só engorda a URL.
    focus_per_day: String(prefs.focusPerDay ?? 10_000),
    spec_items: (prefs.specItems ?? [])
      .filter((s) => s.item.trim() && s.level > 0)
      .map((s) => `${s.item.trim()}:${s.level}`)
      .join(","),
  };
}
