import type { HistoryPoint } from "@/lib/api";
import { formatSilver } from "@/lib/format";

/**
 * Gráfico de linha em SVG puro.
 *
 * Sem biblioteca de chart por dois motivos: o gráfico precisa marcar outliers
 * de um jeito específico (ponto visível, fora da linha de referência), e uma
 * dependência de ~150 kB no bundle não se paga para uma linha e alguns círculos.
 */
const WIDTH = 720;
const HEIGHT = 240;
const PAD = { top: 16, right: 16, bottom: 28, left: 64 };

export function PriceChart({
  points,
  median,
  label,
}: {
  points: HistoryPoint[];
  median: number | null;
  label: string;
}) {
  const limpos = points.filter((point) => !point.is_outlier);
  if (limpos.length < 2) {
    return (
      <p className="py-8 text-muted text-sm">
        Dados insuficientes para traçar a série. Coleta comunitária: mercado pouco
        visitado fica sem histórico.
      </p>
    );
  }

  // A escala usa só os pontos limpos. Incluir o outlier achataria a série inteira
  // contra a base do gráfico e esconderia a variação que importa.
  const valores = limpos.map((point) => point.avg_price);
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const span = max - min || 1;

  const plotW = WIDTH - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;

  const x = (index: number) => PAD.left + (index / (points.length - 1)) * plotW;
  const y = (value: number) =>
    PAD.top + plotH - ((Math.min(Math.max(value, min), max) - min) / span) * plotH;

  const linha = limpos
    .map((point) => {
      const index = points.indexOf(point);
      return `${index === points.indexOf(limpos[0]) ? "M" : "L"} ${x(index)} ${y(point.avg_price)}`;
    })
    .join(" ");

  const ticks = [min, min + span / 2, max];
  const primeiro = new Date(points[0].timestamp);
  const ultimo = new Date(points[points.length - 1].timestamp);
  const dia = (date: Date) =>
    date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Série de preço em ${label}`}
      >
        {ticks.map((value) => (
          <g key={value}>
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={y(value)}
              y2={y(value)}
              stroke="var(--color-line)"
              strokeWidth="1"
            />
            <text
              x={PAD.left - 8}
              y={y(value) + 4}
              textAnchor="end"
              className="figure"
              fontSize="11"
              fill="var(--color-muted)"
            >
              {formatSilver(Math.round(value))}
            </text>
          </g>
        ))}

        {median !== null && median >= min && median <= max && (
          <line
            x1={PAD.left}
            x2={WIDTH - PAD.right}
            y1={y(median)}
            y2={y(median)}
            stroke="var(--color-silver)"
            strokeWidth="1"
            strokeDasharray="4 4"
            opacity="0.5"
          />
        )}

        <path d={linha} fill="none" stroke="var(--color-silver)" strokeWidth="1.5" />

        {/* Outlier: círculo vazado na borda do gráfico. Continua visível, mas
            não distorce a escala nem entra na linha. */}
        {points.map((point, index) =>
          point.is_outlier ? (
            <g key={point.timestamp}>
              <circle
                cx={x(index)}
                cy={PAD.top + 6}
                r="4"
                fill="none"
                stroke="var(--color-warn)"
                strokeWidth="1.5"
              />
              <title>
                {`${formatSilver(point.avg_price)} — marcado como outlier, fora das estatísticas`}
              </title>
            </g>
          ) : null,
        )}

        <text x={PAD.left} y={HEIGHT - 8} fontSize="11" fill="var(--color-muted)" className="figure">
          {dia(primeiro)}
        </text>
        <text
          x={WIDTH - PAD.right}
          y={HEIGHT - 8}
          textAnchor="end"
          fontSize="11"
          fill="var(--color-muted)"
          className="figure"
        >
          {dia(ultimo)}
        </text>
      </svg>
    </figure>
  );
}
