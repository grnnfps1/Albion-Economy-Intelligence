import { formatDataAge, formatSilver } from "@/lib/format";
import { tierBorderLeft } from "@/lib/tiers";

/** Número com o rótulo que diz o que ele já inclui. Rótulo vago esconde taxa. */
export function Figure({
  value,
  label,
  className = "",
}: {
  value: number | null | undefined;
  label: string;
  className?: string;
}) {
  return (
    <div className={`pr-3 text-right ${className}`}>
      <span className="figure text-val">{formatSilver(value)}</span>
      <span className="lbl mt-px block">{label}</span>
    </div>
  );
}

/** Lucro com a margem em pílula — o par que responde "vale a pena?". */
export function ProfitFigure({
  profit,
  marginPct,
  unknownReason,
}: {
  profit: number | null;
  marginPct: number | null;
  unknownReason?: string | null;
}) {
  if (profit === null) {
    return (
      <div className="pr-3 text-right" title={unknownReason ?? undefined}>
        <span className="figure text-dim text-val">UNKNOWN</span>
      </div>
    );
  }

  const positivo = profit > 0;

  return (
    <div className="pr-3 text-right">
      {/* O maior número da linha. Hierarquia por tamanho: se custo, receita e
          lucro tivessem o mesmo peso, nenhum teria peso. */}
      <div
        className={`figure font-semibold text-[15px] leading-none ${
          positivo ? "text-up" : "text-down"
        }`}
      >
        {positivo ? "+" : ""}
        {formatSilver(profit)}
      </div>
      {marginPct !== null && (
        <span
          className={`figure mt-[3px] inline-flex items-center gap-px rounded-[3px] px-[6px] py-px font-bold text-[10px] ${
            positivo ? "bg-up-dim text-up" : "bg-down-dim text-down"
          }`}
        >
          {/* A seta é redundante com a cor, de propósito: cor sozinha não
              chega a quem não distingue verde de vermelho. */}
          <span aria-hidden>{positivo ? "▲" : "▼"}</span>
          {positivo ? "+" : ""}
          {marginPct.toFixed(1)}%
        </span>
      )}
    </div>
  );
}

const TOM: Record<string, string> = {
  ATUALIZADO: "text-up",
  DESATUALIZADO: "text-warn",
  ANTIGO: "text-down",
  DESCONHECIDO: "text-dim",
};

/** Idade abreviada e colorida. Está em toda tela porque o dado é comunitário. */
export function AgeTag({ seconds, freshness }: { seconds: number | null; freshness?: string }) {
  const tom = freshness
    ? TOM[freshness]
    : seconds === null
      ? "text-dim"
      : seconds <= 900
        ? "text-up"
        : seconds <= 21600
          ? "text-warn"
          : "text-down";
  return <span className={`figure text-[9.5px] ${tom}`}>{formatDataAge(seconds)}</span>;
}

/**
 * Linha densa: faixa de tier à esquerda, fundo tingido pelo resultado.
 *
 * O zebrado é fraco de propósito (2% de branco). Numa linha de sete colunas o
 * olho perde a horizontal no meio do caminho, e o zebrado é o que o segura —
 * mas forte demais ele briga com o tingimento de lucro, que é informação de
 * verdade. Quando a linha tem resultado, o tingimento vence e o zebrado sai.
 */
export function DenseRow({
  tier,
  positive,
  children,
  columns,
  index = 0,
}: {
  tier: number | null;
  positive?: boolean | null;
  columns: string;
  children: React.ReactNode;
  index?: number;
}) {
  const tinta =
    positive === true
      ? "bg-[linear-gradient(90deg,rgba(86,192,127,0.08),transparent_32%)]"
      : positive === false
        ? "bg-[linear-gradient(90deg,rgba(226,85,92,0.08),transparent_32%)]"
        : index % 2 === 1
          ? "bg-white/[0.015]"
          : "";

  return (
    <div
      className={`grid items-center border-line/60 border-b border-l-[3px] py-2 pr-4 pl-3 transition-colors duration-100 hover:bg-white/[0.035] ${tierBorderLeft(tier)} ${tinta}`}
      style={{ gridTemplateColumns: columns }}
    >
      {children}
    </div>
  );
}
