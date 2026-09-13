import { formatDataAge, formatSilver } from "@/lib/format";

/** Número com o rótulo que diz o que ele já inclui. Rótulo vago esconde taxa. */
export function Figure({
  value, label, className = "",
}: {
  value: number | null | undefined;
  label: string;
  className?: string;
}) {
  return (
    <div className={`pr-3 text-right ${className}`}>
      <span className="figure text-[12.5px]">{formatSilver(value)}</span>
      <span className="mt-px block text-[9px] text-dim uppercase tracking-[0.05em]">{label}</span>
    </div>
  );
}

/** Lucro com a margem em pílula — o par que responde "vale a pena?". */
export function ProfitFigure({
  profit, marginPct, unknownReason,
}: {
  profit: number | null;
  marginPct: number | null;
  unknownReason?: string | null;
}) {
  if (profit === null) {
    return (
      <div className="pr-3 text-right" title={unknownReason ?? undefined}>
        <span className="figure text-[12.5px] text-dim">UNKNOWN</span>
      </div>
    );
  }
  const positivo = profit > 0;
  return (
    <div className="pr-3 text-right">
      <div className={`figure font-semibold text-[15px] leading-none ${positivo ? "text-up" : "text-down"}`}>
        {positivo ? "+" : ""}
        {formatSilver(profit)}
      </div>
      {marginPct !== null && (
        <span
          className={`figure mt-[3px] inline-block rounded-[3px] px-[6px] py-px font-bold text-[10px] ${
            positivo ? "bg-up-dim text-up" : "bg-down-dim text-down"
          }`}
        >
          {positivo ? "+" : ""}
          {marginPct.toFixed(1)}%
        </span>
      )}
    </div>
  );
}

const TOM: Record<string, string> = {
  ATUALIZADO: "text-up", DESATUALIZADO: "text-warn",
  ANTIGO: "text-down", DESCONHECIDO: "text-dim",
};

/** Idade abreviada e colorida. Está em toda tela porque o dado é comunitário. */
export function AgeTag({
  seconds, freshness,
}: {
  seconds: number | null;
  freshness?: string;
}) {
  const tom = freshness
    ? TOM[freshness]
    : seconds === null ? "text-dim"
    : seconds <= 900 ? "text-up"
    : seconds <= 21600 ? "text-warn"
    : "text-down";
  return <span className={`figure text-[9.5px] ${tom}`}>{formatDataAge(seconds)}</span>;
}

/** Linha densa com faixa de tier e fundo tingido pelo resultado. */
export function DenseRow({
  tier, positive, children, columns,
}: {
  tier: number | null;
  positive?: boolean | null;
  columns: string;
  children: React.ReactNode;
}) {
  const TIER_BORDA: Record<number, string> = {
    1: "border-l-t1", 2: "border-l-t2", 3: "border-l-t3", 4: "border-l-t4",
    5: "border-l-t5", 6: "border-l-t6", 7: "border-l-t7", 8: "border-l-t8",
  };
  const tinta =
    positive === true
      ? "bg-[linear-gradient(90deg,rgba(63,191,127,0.07),transparent_30%)]"
      : positive === false
        ? "bg-[linear-gradient(90deg,rgba(226,85,92,0.07),transparent_30%)]"
        : "";
  return (
    <div
      className={`grid items-center border-line border-b border-l-[3px] py-1.5 pr-4 pl-3 hover:bg-white/[0.028] ${
        TIER_BORDA[tier ?? 0] ?? "border-l-transparent"
      } ${tinta}`}
      style={{ gridTemplateColumns: columns }}
    >
      {children}
    </div>
  );
}
