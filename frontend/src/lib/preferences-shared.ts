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
  stationFee: number;
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
};

export const DEFAULTS: Preferences = {
  server: "west",
  buyLocation: "caerleon",
  sellLocation: "caerleon",
  premium: true,
  setupFeePct: 0.025,
  salesTaxPct: 0.04,
  returnRate: 0.15,
  stationFee: 100,
  focusBudget: 10_000,
  quantity: 100,
  lossPctBlue: 0,
  lossPctRedBlack: 0,
  useFocus: false,
  dailyProductionBonus: 0,
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
    station_fee: String(prefs.stationFee),
    use_focus: String(prefs.useFocus),
    daily_production_bonus: String(prefs.dailyProductionBonus),
    loss_pct_blue: String(prefs.lossPctBlue),
    loss_pct_red_black: String(prefs.lossPctRedBlack),
  };
}
