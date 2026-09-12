import type { PriceField } from "@/lib/api";
import { formatSilver } from "@/lib/format";

import { FreshnessTag } from "./FreshnessTag";

/**
 * Um preço e a idade dele.
 *
 * Sem cotação, mostra "sem dado" — nunca 0. Ausência de ordem e preço zero são
 * coisas diferentes, e confundi-las faz o usuário comprar uma oportunidade que
 * não existe.
 */
export function PriceCell({ field }: { field: PriceField }) {
  if (field.value === null) {
    return <span className="text-muted text-xs">sem dado</span>;
  }
  return (
    <span className="flex flex-col items-end leading-tight">
      <span className="figure text-body text-sm">{formatSilver(field.value)}</span>
      <FreshnessTag freshness={field.freshness} ageSeconds={field.age_seconds} />
    </span>
  );
}
