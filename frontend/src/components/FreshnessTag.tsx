import type { Freshness } from "@/lib/api";
import { formatDataAge } from "@/lib/format";

const TONE: Record<Freshness, string> = {
  ATUALIZADO: "text-up",
  DESATUALIZADO: "text-warn",
  ANTIGO: "text-down",
  DESCONHECIDO: "text-muted",
};

/**
 * Idade do dado, sempre visível.
 *
 * Os preços vêm de coleta comunitária e podem ser de dias atrás. Esconder a
 * idade faria o usuário decidir com informação morta.
 */
export function FreshnessTag({
  freshness,
  ageSeconds,
}: {
  freshness: Freshness;
  ageSeconds: number | null;
}) {
  return (
    <span className={`figure text-xs ${TONE[freshness]}`}>{formatDataAge(ageSeconds)}</span>
  );
}
