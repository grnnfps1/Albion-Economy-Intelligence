/**
 * Formatação de apresentação.
 *
 * Regra: estas funções NÃO calculam nada de negócio. Lucro, margem, ROI e score
 * vêm prontos do backend (requisito 54). Aqui só se transforma número em texto.
 */

/** Prata sempre com separador de milhar pt-BR. */
export function formatSilver(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("pt-BR").format(value);
}

/**
 * Abaixo disto **não** se abrevia.
 *
 * `9,9K` é menos legível que `9.870` e ainda perde precisão — troca ruim nos
 * dois lados. A abreviação só compensa quando o número cheio de fato não cabe.
 */
export const LIMIAR_DE_ABREVIACAO = 10_000;

const SUFIXOS = [
  { limite: 1_000_000_000, sufixo: "B" },
  { limite: 1_000_000, sufixo: "M" },
  { limite: 1_000, sufixo: "K" },
] as const;

/**
 * Prata abreviada: `133,1M`, `1,2B`, `12,5K`.
 *
 * ## Por que isto voltou depois de a fase 18 tê-lo removido
 *
 * A fase 18 escreveu "número cheio, nunca abreviado" e estava certa **para os
 * valores que existiam então**: unitários, de quatro a seis dígitos, onde
 * abreviar economizava o que não precisava ser economizado e custava precisão.
 *
 * O calculador mudou os dados, não a regra: ele mostra produções inteiras, e
 * `133.086.292` tem nove dígitos. A regra antiga aplicada a esses números não
 * dá "precisão" — dá coluna estourada e valor truncado pelo navegador, que é
 * pior que arredondado de propósito.
 *
 * Por isso a reversão é **parcial** e tem fronteira explícita:
 *
 * - abrevia-se o **contexto** (custo, receita, taxas, investimento);
 * - **lucro** continua cheio, porque é o número que decide e `133.086.292` e
 *   `133.086.291` são coisas diferentes na hora de conferir;
 * - **campo de preço editável** continua cheio, porque abreviar o que se digita
 *   cria ambiguidade na volta — `4,5K` digitado de volta é 4.500 ou 4.532?
 * - **exportação nunca abrevia**: planilha soma número, não texto.
 *
 * O valor exato acompanha toda célula abreviada, no balão, para conferência
 * sem sair da tela.
 */
export function formatSilverCompact(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (Math.abs(value) < LIMIAR_DE_ABREVIACAO) return formatSilver(value);

  for (const { limite, sufixo } of SUFIXOS) {
    if (Math.abs(value) >= limite) {
      // `toFixed` trunca para uma casa e a vírgula é a decimal do pt-BR — a
      // mesma escolha do resto do produto.
      return `${(value / limite).toFixed(1).replace(".", ",")}${sufixo}`;
    }
  }
  return formatSilver(value);
}

/**
 * Idade do dado em texto curto.
 * `null` significa "não há dado", e é diferente de "0 segundos" (requisito 52).
 */
export function formatDataAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "sem dado";
  if (seconds < 60) return "agora";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `há ${hours} h`;
  const days = Math.floor(hours / 24);
  return `há ${days} d`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return `${new Intl.NumberFormat("pt-BR").format(ms)} ms`;
}

export type StatusTone = "ok" | "degraded" | "down" | "unknown";

export function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case "ok":
      return "operacional";
    case "degraded":
      return "parcial";
    case "down":
      return "fora do ar";
    default:
      return "desconhecido";
  }
}

export function statusTone(status: string | null | undefined): StatusTone {
  if (status === "ok" || status === "degraded" || status === "down") return status;
  return "unknown";
}
