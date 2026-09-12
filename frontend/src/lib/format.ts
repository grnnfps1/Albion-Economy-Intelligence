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
