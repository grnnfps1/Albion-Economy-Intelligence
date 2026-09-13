import type { Trend } from "@/lib/api";

const LABEL: Record<Trend, { text: string; tone: string }> = {
  ALTA: { text: "alta", tone: "text-up" },
  BAIXA: { text: "baixa", tone: "text-down" },
  ESTAVEL: { text: "estável", tone: "text-muted" },
  DESCONHECIDA: { text: "sem tendência", tone: "text-muted" },
};

export function TrendTag({ trend, changePct }: { trend: Trend; changePct: number | null }) {
  const { text, tone } = LABEL[trend];
  return (
    <span className={`text-sm ${tone}`}>
      {text}
      {changePct !== null && (
        <span className="figure ml-1.5 text-xs">
          {changePct > 0 ? "+" : ""}
          {changePct.toFixed(1)}%
        </span>
      )}
    </span>
  );
}
