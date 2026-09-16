import { formatSilver } from "@/lib/format";
import { tierBg } from "@/lib/tiers";

/** Tier e encantamento no formato do jogo: `T7.2`. */
export function TierBadge({ tier, enchantment = 0 }: { tier: number | null; enchantment?: number }) {
  return (
    <span
      className={`figure rounded-[3px] px-[5px] py-px font-bold text-[9.5px] text-ink ${tierBg(tier)}`}
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
 *
 * `alternate` marca a compra que sai da cidade base. Sem a marca, uma linha com
 * quatro cidades diferentes parece igual a uma linha com uma só — e é a
 * diferença entre uma viagem e quatro.
 */
export function CityTag({
  city,
  className = "",
  alternate = false,
}: {
  city: string;
  className?: string;
  alternate?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-[5px] ${
        alternate ? "rounded-[3px] bg-warn/10 px-[3px] font-semibold text-warn" : ""
      } ${className}`}
    >
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

/**
 * Aviso de rota espalhada.
 *
 * Economizar 3% em quatro cidades não é economia: são quatro viagens, quatro
 * janelas de tempo em que o preço muda e quatro chances de a ordem sumir antes
 * de você chegar. Por isso o número de cidades aparece junto com a economia, e
 * nunca a economia sozinha.
 */
export function SpreadWarning({
  cities,
  savings,
  savingsPct,
}: {
  cities: number;
  savings?: number | null;
  savingsPct?: number | null;
}) {
  if (cities <= 2) return null;

  const economia =
    savings === null || savings === undefined
      ? "economia desconhecida"
      : `economiza ${formatSilver(savings)}${
          savingsPct === null || savingsPct === undefined ? "" : ` (${savingsPct.toFixed(1)}%)`
        }`;

  return (
    <span
      title={`A rota passa por ${cities} cidades e ${economia}. Compare com o tempo de viagem antes de aceitar.`}
      className="figure shrink-0 rounded-[3px] border border-warn/40 bg-warn/10 px-[5px] py-px font-bold text-[9.5px] text-warn"
    >
      ⚠ {cities} cidades
    </span>
  );
}
