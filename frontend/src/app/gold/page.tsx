import { PriceChart } from "@/components/PriceChart";
import { TrendTag } from "@/components/TrendTag";
import { fetchGold } from "@/lib/api";
import { formatSilver } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function GoldPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const server = (Array.isArray(raw.server) ? raw.server[0] : raw.server) ?? "west";
  const days = (Array.isArray(raw.days) ? raw.days[0] : raw.days) ?? "7";

  const data = await fetchGold(server, days);

  return (
    <div>
      <header className="mb-6">
        <h1 className="font-semibold text-2xl text-body tracking-tight">Gold</h1>
        <p className="mt-2 max-w-prose text-muted text-sm leading-relaxed">
          Cotação de gold em prata. O endpoint do AODP não informa o servidor — ele vem do
          host consultado, então a série é sempre de um servidor só.
        </p>
      </header>

      {data === null || data.points.length === 0 ? (
        <div className="rounded-sm border border-line bg-ink-raised p-4 text-sm">
          <p className="text-body">Sem cotação registrada.</p>
          <p className="mt-1 text-muted">
            Rode{" "}
            <code className="figure text-body">
              docker compose exec backend python -m app.cli.collect_history --gold --server{" "}
              {server}
            </code>
            .
          </p>
        </div>
      ) : (
        <>
          <div className="mb-4 flex items-end justify-between gap-4">
            <p className="figure text-3xl text-body">{formatSilver(data.current)}</p>
            <TrendTag trend={data.trend} changePct={data.change_pct} />
          </div>

          <PriceChart
            points={data.points.map((point) => ({
              timestamp: point.timestamp,
              avg_price: point.price,
              item_count: 0,
              is_outlier: false,
            }))}
            median={data.median}
            label="Gold"
          />

          <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2 text-xs">
            <span className="flex gap-1.5">
              <dt className="text-muted">mediana</dt>
              <dd className="figure text-body">
                {data.median === null ? "—" : formatSilver(Math.round(data.median))}
              </dd>
            </span>
            <span className="flex gap-1.5">
              <dt className="text-muted">mínimo</dt>
              <dd className="figure text-body">{formatSilver(data.minimum)}</dd>
            </span>
            <span className="flex gap-1.5">
              <dt className="text-muted">máximo</dt>
              <dd className="figure text-body">{formatSilver(data.maximum)}</dd>
            </span>
            <span className="flex gap-1.5">
              <dt className="text-muted">pontos</dt>
              <dd className="figure text-body">{data.points.length}</dd>
            </span>
          </dl>
        </>
      )}
    </div>
  );
}
