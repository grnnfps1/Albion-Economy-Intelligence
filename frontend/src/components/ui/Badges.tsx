const TIER_BG: Record<number, string> = {
  1: "bg-t1", 2: "bg-t2", 3: "bg-t3", 4: "bg-t4",
  5: "bg-t5", 6: "bg-t6", 7: "bg-t7", 8: "bg-t8",
};

/** Tier e encantamento no formato do jogo: `T7.2`. */
export function TierBadge({ tier, enchantment = 0 }: { tier: number | null; enchantment?: number }) {
  return (
    <span
      className={`figure rounded-[3px] px-[5px] py-px font-bold text-[9.5px] text-ink ${
        TIER_BG[tier ?? 0] ?? "bg-line-strong"
      }`}
    >
      T{tier ?? "?"}.{enchantment}
    </span>
  );
}

const QUALIDADES = ["NORMAL", "BOM", "EXCEPCIONAL", "EXCELENTE", "OBRA-PRIMA"];

export function QualityBadge({ quality }: { quality: number }) {
  const alta = quality >= 4;
  return (
    <span
      className={`figure rounded-[3px] border px-[5px] py-px font-bold text-[9.5px] ${
        alta ? "border-warn/40 bg-warn/10 text-warn" : "border-line bg-raised text-muted"
      }`}
    >
      {QUALIDADES[quality - 1] ?? `Q${quality}`}
    </span>
  );
}

const CIDADE_COR: Record<string, string> = {
  Caerleon: "bg-caerleon",
  Bridgewatch: "bg-bridgewatch",
  Lymhurst: "bg-lymhurst",
  "Fort Sterling": "bg-fortsterling",
  Martlock: "bg-martlock",
  Thetford: "bg-thetford",
  Brecilien: "bg-brecilien",
};

/**
 * Cidade sempre com o nome escrito.
 *
 * O ponto colorido acelera quem já conhece as cores; o nome evita que quem não
 * conhece precise decorar sete delas.
 */
export function CityTag({ city, className = "" }: { city: string; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-[5px] ${className}`}>
      <span
        aria-hidden
        className={`inline-block size-[5px] shrink-0 rounded-full ${
          CIDADE_COR[city] ?? "bg-line-strong"
        }`}
      />
      <span className="truncate">{city}</span>
    </span>
  );
}
