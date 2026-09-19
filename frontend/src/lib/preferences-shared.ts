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
   * na tela da estação. Substituiu a taxa fixa por craft na fase 15: a taxa
   * real sai de `item_value × 0,1125 × isto ÷ 100`, e por isso escala com tier
   * e encantamento em vez de ser a mesma no T2 e no T8.
   */
  stationFeePer100Nutrition: number;
  focusBudget: number;
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
  // Mediana das três taxas que os resíduos da planilha do Albion VIP
  // implicam (1.149 / 1.666 / 8.669). Não é medição no jogo — o formulário diz
  // isso — mas tem procedência, ao contrário de um 100 redondo.
  stationFeePer100Nutrition: 1666,
  focusBudget: 10_000,
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
    station_fee_per_100_nutrition: String(prefs.stationFeePer100Nutrition),
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
    spec_items: (prefs.specItems ?? [])
      .filter((s) => s.item.trim() && s.level > 0)
      .map((s) => `${s.item.trim()}:${s.level}`)
      .join(","),
  };
}
