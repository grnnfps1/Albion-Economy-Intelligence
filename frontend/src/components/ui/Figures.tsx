import { formatDataAge, formatSilver } from "@/lib/format";

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
 * Lucro bruto e lucro ajustado ao risco, na mesma célula.
 *
 * O ajustado é o número grande porque é o que decide. O bruto fica embaixo,
 * menor, porque sem ele o desconto não é auditável — um número que já vem
 * descontado, sozinho, esconde de onde veio.
 *
 * Quando o usuário não modelou perda os dois são iguais, e aí **um só aparece**:
 * repetir o mesmo número duas vezes gastaria espaço e faria parecer que há uma
 * diferença onde não há.
 */
export function RiskProfitFigure({
  grossProfit,
  expectedProfit,
  lossProbability,
  crossesOpenWorld,
  unknownReason,
  marginPct,
}: {
  grossProfit: number | null;
  expectedProfit: number | null;
  lossProbability: number;
  crossesOpenWorld: boolean;
  unknownReason?: string | null;
  marginPct?: number | null;
}) {
  if (grossProfit === null) {
    return (
      <ProfitFigure
        profit={null}
        marginPct={null}
        unknownReason={unknownReason}
      />
    );
  }

  const modelado = lossProbability > 0;
  if (!modelado) {
    return (
      <div className="pr-3 text-right">
        <ProfitFigure
          profit={grossProfit}
          marginPct={marginPct ?? null}
        />
        {crossesOpenWorld && (
          <span className="lbl mt-px block text-dim" title="Informe a perda esperada nas preferências para ver o lucro ajustado ao risco.">
            risco não modelado
          </span>
        )}
      </div>
    );
  }

  const ajustado = expectedProfit ?? 0;
  const positivo = ajustado > 0;
  const perdeu = grossProfit - ajustado;

  return (
    <div
      className="pr-3 text-right"
      title={`Bruto ${formatSilver(grossProfit)}. Com ${(lossProbability * 100).toFixed(1)}% de chance de perder a carga, o esperado cai para ${formatSilver(ajustado)} — a perda leva junto o que foi investido, não só o lucro.`}
    >
      <div
        className={`figure font-semibold text-[15px] leading-none ${
          positivo ? "text-up" : "text-down"
        }`}
      >
        {positivo ? "+" : ""}
        {formatSilver(ajustado)}
      </div>
      <div className="mt-[3px] flex items-center justify-end gap-1">
        <span className="lbl text-dim">bruto</span>
        <span className="figure text-[10px] text-muted line-through">
          {formatSilver(grossProfit)}
        </span>
      </div>
      <span className="figure mt-px block text-[9.5px] text-down">
        −{formatSilver(perdeu)} de risco
      </span>
    </div>
  );
}
