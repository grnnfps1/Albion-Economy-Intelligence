import type { Liquidity } from "@/lib/api";
import { formatSilver } from "@/lib/format";

/**
 * Giro e cobertura do histórico.
 *
 * Dois sinais diferentes no mesmo bloco: quanto o item gira por dia, e em
 * quantos dos últimos 30 dias existe registro. Preço fresco com cobertura de
 * 3/30 é frágil — o mercado quase não é visitado, e a próxima cotação pode ser
 * muito diferente.
 *
 * Sem histórico suficiente, mostra "liquidez desconhecida". Não é erro: é o
 * estado honesto de um mercado que ninguém abriu (requisito 21).
 */
export function LiquidityBar({ liquidity }: { liquidity: Liquidity }) {
  if (liquidity.status === "UNKNOWN") {
    return <span className="text-muted text-xs">liquidez desconhecida</span>;
  }

  const cobertura = Math.min(1, liquidity.days_with_data / liquidity.period_days);
  const tom = cobertura >= 0.7 ? "bg-up" : cobertura >= 0.3 ? "bg-warn" : "bg-down";

  return (
    <span className="flex items-center gap-2">
      <span className="figure text-body text-xs">
        {formatSilver(Math.round(liquidity.units_per_day ?? 0))}/dia
      </span>
      <span
        className="h-1 w-12 overflow-hidden rounded-full bg-line"
        title={`histórico em ${liquidity.days_with_data} de ${liquidity.period_days} dias`}
      >
        <span className={`block h-full ${tom}`} style={{ width: `${cobertura * 100}%` }} />
      </span>
      <span className="figure text-muted text-xs">
        {liquidity.days_with_data}/{liquidity.period_days}d
      </span>
    </span>
  );
}
